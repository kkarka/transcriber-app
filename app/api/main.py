import os
import shutil
import uuid
import boto3

from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from prometheus_fastapi_instrumentator import Instrumentator

from redis import Redis
from rq.job import Job
from rq.exceptions import NoSuchJobError
from rq.command import send_stop_job_command

from pydantic import BaseModel
from sqlalchemy.orm import Session

# Import your local modules
from redis_queue import transcription_queue
from database import engine, wait_for_db, Base
import models
import database

# -------------------------
# DATABASE SETUP
# -------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    if wait_for_db():
        models.Base.metadata.create_all(bind=database.engine)
    yield

# Default to an empty string for local development
API_PREFIX = os.getenv("API_PREFIX", "")

app = FastAPI(title="Transcriber App", version="1.0.0", lifespan=lifespan, root_path=API_PREFIX)

# -------------------------
# METRICS (PROMETHEUS)
# -------------------------
Instrumentator().instrument(app).expose(app)

# -------------------------
# PYDANTIC CONTRACTS
# -------------------------
class PreSignRequest(BaseModel):
    filename: str
    content_type: str

class PreSignResponse(BaseModel):
    job_id: str
    upload_url: str
    file_identifier: str

class StartTranscriptionRequest(BaseModel):
    job_id: str
    file_identifier: str

# -------------------------
# CORS CONFIG
# -------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# CONFIG
# -------------------------
UPLOAD_DIR = "uploads"
ALLOWED_EXTENSIONS = (".mp4", ".mov", ".mkv", ".webm", ".avi")

os.makedirs(UPLOAD_DIR, exist_ok=True)

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
redis_conn = Redis(host=REDIS_HOST, port=6379)

STORAGE_MODE = os.getenv("STORAGE_MODE", "local")
S3_BUCKET = os.getenv("S3_VIDEO_BUCKET_NAME")
s3_client = boto3.client('s3') if STORAGE_MODE == "s3" else None

# -------------------------
# ROOT
# -------------------------
@app.get("/")
def read_root():
    return {"message": "Transcription API running"}

# -------------------------
# STEP 1: GENERATE UPLOAD URL
# -------------------------
@app.post("/v1/upload/presign", response_model=PreSignResponse)
def generate_upload_url(
    request: PreSignRequest, 
    api_req: Request, 
    db: Session = Depends(database.get_db)
):
    filename = request.filename.lower()
    if not filename.endswith(ALLOWED_EXTENSIONS):
        raise HTTPException(status_code=400, detail="Unsupported file type")

    # 1. Create DB Record first so we have an ID
    new_job = models.TranscriptionJob(filename=request.filename, status=models.JobStatus.PENDING)
    db.add(new_job)
    db.commit()
    db.refresh(new_job)

    unique_filename = f"{new_job.id}_{request.filename}"

    # 2. Generate the routing based on STORAGE_MODE
    if STORAGE_MODE == "s3":
        # Production: Give React the AWS S3 URL
        try:
            upload_url = s3_client.generate_presigned_url(
                'put_object',
                Params={
                    'Bucket': S3_BUCKET, 
                    'Key': unique_filename, 
                    'ContentType': request.content_type
                },
                ExpiresIn=3600 # 1 hour timeout
            )
            file_identifier = f"s3://{S3_BUCKET}/{unique_filename}"
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Could not generate S3 URL: {str(e)}")
    else:
        # Local Dev: Give React a URL pointing back to this local server
        base_url = str(api_req.base_url).rstrip("/")
        upload_url = f"{base_url}{API_PREFIX}/v1/upload/local/{new_job.id}"
        file_identifier = os.path.abspath(os.path.join(UPLOAD_DIR, unique_filename))

    return {
        "job_id": str(new_job.id),
        "upload_url": upload_url,
        "file_identifier": file_identifier
    }

# -------------------------
# STEP 1.5: LOCAL DEV FILE CATCHER
# -------------------------
@app.put("/v1/upload/local/{job_id}")
async def local_dev_upload(job_id: str, request: Request, db: Session = Depends(database.get_db)):
    """This endpoint is ONLY used during local development to catch the raw file PUT."""
    if STORAGE_MODE != "local":
        raise HTTPException(status_code=400, detail="Local upload is disabled in S3 mode")

    db_job = db.query(models.TranscriptionJob).filter(models.TranscriptionJob.id == job_id).first()
    if not db_job:
        raise HTTPException(status_code=404, detail="Job not found")

    unique_filename = f"{db_job.id}_{db_job.filename}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)

    # Stream the raw binary data from the React PUT request directly to disk
    with open(file_path, "wb") as buffer:
        async for chunk in request.stream():
            buffer.write(chunk)

    return {"message": "Local upload complete"}

# -------------------------
# STEP 2: START TRANSCRIPTION
# -------------------------
@app.post("/v1/transcribe/start")
def start_transcription(
    request: StartTranscriptionRequest,
    db: Session = Depends(database.get_db)
):
    db_job = db.query(models.TranscriptionJob).filter(models.TranscriptionJob.id == request.job_id).first()
    if not db_job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    db_job.status = models.JobStatus.PROCESSING
    db.commit()

    # Push to Redis queue
    transcription_queue.enqueue(
        "tasks.transcribe",
        args=(db_job.id, request.file_identifier),
        job_id=str(db_job.id),
        job_timeout="2h" # Generous timeout for massive files
    )

    return {"status": "processing", "job_id": str(db_job.id)}

# -------------------------
# JOB STATUS (v1)
# -------------------------
@app.get("/v1/status/{job_id}")
def get_status(job_id: str, db: Session = Depends(database.get_db)):
    db_job = db.query(models.TranscriptionJob).filter(models.TranscriptionJob.id == job_id).first()
    
    if not db_job:
        raise HTTPException(status_code=404, detail="Job not found in database")

    if db_job.status in [models.JobStatus.COMPLETED, models.JobStatus.FAILED]:
        return {
            "status": db_job.status.value.lower(),
            "progress": 100 if db_job.status == models.JobStatus.COMPLETED else 0,
            "stage": "Completed" if db_job.status == models.JobStatus.COMPLETED else "Failed",
            "result": db_job.transcript,
            "error_message": db_job.error_message
        }

    progress = redis_conn.get(f"progress:{job_id}")
    stage = redis_conn.get(f"stage:{job_id}")

    return {
        "status": db_job.status.value.lower(),
        "progress": int(progress) if progress else 0,
        "stage": stage.decode('utf-8') if stage else "Initializing job...",
        "result": None
    }

# -------------------------
# CANCEL JOB (v1)
# -------------------------
@app.post("/v1/cancel/{job_id}")
def cancel_job(job_id: str, db: Session = Depends(database.get_db)):
    db_job = db.query(models.TranscriptionJob).filter(models.TranscriptionJob.id == job_id).first()
    if not db_job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    db_job.status = models.JobStatus.FAILED
    db_job.error_message = "Cancelled by user"
    db.commit()

    try:
        send_stop_job_command(redis_conn, job_id)
    except NoSuchJobError:
        pass 

    return {"status": "cancelled", "job_id": job_id}