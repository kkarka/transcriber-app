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
from openai import AsyncOpenAI

# Import your local modules
from redis_queue import transcription_queue
from database import engine, wait_for_db, Base
import models
import database

from fastapi.responses import StreamingResponse
import asyncio


# Initialize the async client. 
# It automatically picks up HUGGINGFACE_API_KEY from your environment.
aclient = AsyncOpenAI(
    api_key=os.getenv("HUGGINGFACE_API_KEY"),
    base_url="https://router.huggingface.co/v1" # 
)


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

class NotesRequest(BaseModel):
    transcription: str


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

# REDIS_HOST = os.getenv("REDIS_HOST", "localhost") # Default to localhost for local dev, but in Kubernetes it should be set to 'redis-master' as per the redis-setup.yaml
REDIS_HOST = os.getenv("REDIS_HOST", "redis-master")
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
# HEALTH CHECK
# -------------------------
@app.get("/health")
def health():
    return {"status": "ok"}


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
# Notes Generator Function
# -------------------------
async def real_llm_stream(transcription_text: str):
    prompt = f"""
    You are an expert executive assistant. Please read the following transcription 
    and provide a beautifully formatted summary, key takeaways, and any action items.
    Use Markdown formatting (bullet points, bold text, etc.).
    
    Transcription:
    {transcription_text}
    """
    
    try:
        stream = await aclient.chat.completions.create(
            # 2. Use a powerful, free Hugging Face model
            model="meta-llama/Meta-Llama-3-8B-Instruct:novita", 
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            stream=True,
            max_tokens=1000 # Good safety limit for the free tier
        )
        
        async for chunk in stream:
            if chunk.choices and len(chunk.choices) > 0:
                content = chunk.choices[0].delta.content
                if content is not None:
                    yield content
                
    except Exception as e:
        yield f"\n\n**Error connecting to AI:** {str(e)}"

# Endpoint remains the same
@app.post("/v1/notes/generate")
async def generate_notes(request: NotesRequest):
    return StreamingResponse(
        real_llm_stream(request.transcription), 
        media_type="text/event-stream"
    )

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