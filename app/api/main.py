import os
import shutil
import uuid

from fastapi import FastAPI, UploadFile, File, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from prometheus_fastapi_instrumentator import Instrumentator

from redis import Redis
from rq.job import Job
from rq.exceptions import NoSuchJobError
from rq.command import send_stop_job_command

from pydantic import BaseModel, HttpUrl
from sqlalchemy.orm import Session

# Import your local modules
from redis_queue import transcription_queue
from database import engine, wait_for_db, Base
import models
import database

# -------------------------
# DATABASE SETUP
# -------------------------
# Create the tables (In production, use Alembic for migrations!)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # This runs BEFORE the server starts accepting requests
    if wait_for_db():
        models.Base.metadata.create_all(bind=database.engine)
    yield
    # Anything below 'yield' runs during server shutdown
app = FastAPI(title="Transcriber App", version="1.0.0", lifespan=lifespan)


# -------------------------
# METRICS (PROMETHEUS)
# -------------------------
Instrumentator().instrument(app).expose(app)

# -------------------------
# PYDANTIC CONTRACTS
# -------------------------
class YoutubeRequest(BaseModel):
    url: HttpUrl

class JobResponse(BaseModel):
    job_id: str
    status: str
    message: str | None = None

# -------------------------
# CORS CONFIG
# -------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows port 5173 to talk to port 8000, change in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# CONFIG
# -------------------------
UPLOAD_DIR = "uploads"
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB
ALLOWED_EXTENSIONS = (".mp4", ".mov", ".mkv")

os.makedirs(UPLOAD_DIR, exist_ok=True)
redis_conn = Redis(host="redis", port=6379)

# -------------------------
# ROOT
# -------------------------
@app.get("/")
def read_root():
    return {"message": "Transcription API running"}

# -------------------------
# UPLOAD + QUEUE JOB (v1)
# -------------------------
@app.post("/v1/transcribe", response_model=JobResponse)
async def transcribe_video(
    file: UploadFile = File(...), 
    db: Session = Depends(database.get_db),
):
    filename = file.filename.lower()

    if not filename.endswith(ALLOWED_EXTENSIONS):
        raise HTTPException(status_code=400, detail="Unsupported file type")

    unique_filename = f"{uuid.uuid4()}_{filename}"
    file_path = os.path.abspath(os.path.join(UPLOAD_DIR, unique_filename))

    with open(file_path, "wb") as buffer:
        while chunk := await file.read(1024 * 1024):
            buffer.write(chunk)
            
    # 1. Create Single Source of Truth in Postgres
    new_job = models.TranscriptionJob(filename=filename, status=models.JobStatus.PENDING)
    db.add(new_job)
    db.commit()
    db.refresh(new_job)

    # 2. Push to Redis queue, keeping the RQ job_id identical to the DB id
    job = transcription_queue.enqueue(
        "tasks.transcribe",
        args=(new_job.id, file_path), # We now pass the DB ID to the worker!
        job_id=new_job.id,
        job_timeout="30m"
    )

    return {"job_id": new_job.id, "status": new_job.status.value, "message": "File processing queued"}


@app.post("/v1/transcribe-youtube", response_model=JobResponse)
async def transcribe_youtube(
    data: YoutubeRequest, 
    db: Session = Depends(database.get_db)
):
    # 1. Record the intent in DB
    new_job = models.TranscriptionJob(filename=str(data.url), status=models.JobStatus.PENDING)
    db.add(new_job)
    db.commit()
    db.refresh(new_job)

    # 2. Queue the job
    job = transcription_queue.enqueue(
        "tasks.transcribe_youtube_job",
        args=(new_job.id, str(data.url)), # Pass DB ID to worker
        job_id=new_job.id,
        job_timeout="45m"
    )

    return {"job_id": new_job.id, "status": new_job.status.value, "message": "YouTube download and transcription queued"}


# -------------------------
# JOB STATUS (v1)
# -------------------------
@app.get("/v1/status/{job_id}")
def get_status(job_id: str, db: Session = Depends(database.get_db)):
    # ALWAYS check Postgres first. This survives Redis TTL expirations and worker crashes.
    db_job = db.query(models.TranscriptionJob).filter(models.TranscriptionJob.id == job_id).first()
    
    if not db_job:
        raise HTTPException(status_code=404, detail="Job not found in database")

    # If the DB says it's done or failed, we don't even need to query Redis
    if db_job.status in [models.JobStatus.COMPLETED, models.JobStatus.FAILED]:
        return {
            "status": db_job.status.value.lower(),
            "progress": 100 if db_job.status == models.JobStatus.COMPLETED else 0,
            "stage": "Completed" if db_job.status == models.JobStatus.COMPLETED else "Failed",
            "result": db_job.transcript,
            "error_message": db_job.error_message
        }

    # If it's still processing, check Redis for live, granular progress updates
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
    # 1. Find in DB
    db_job = db.query(models.TranscriptionJob).filter(models.TranscriptionJob.id == job_id).first()
    if not db_job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    # 2. Update DB status
    db_job.status = models.JobStatus.FAILED
    db_job.error_message = "Cancelled by user"
    db.commit()

    # 3. Stop in Redis
    try:
        send_stop_job_command(redis_conn, job_id)
    except NoSuchJobError:
        pass # It might have already finished or died

    return {"status": "cancelled", "job_id": job_id}