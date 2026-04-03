import os
import boto3
import logging
import redis
from urllib.parse import urlparse
from rq import get_current_job
from faster_whisper import WhisperModel

# Import your database and models
# Ensure your PYTHONPATH includes /shared and /app
from database import SessionLocal, wait_for_db, engine
import models 

s3_client = boto3.client('s3')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -------------------------------------------------
# 1. DATABASE RESILIENCE
# -------------------------------------------------
# This pauses the worker on startup until Postgres is actually ready
if os.getenv("ENV") != "testing":
    if not wait_for_db():
        logger.critical("Worker could not connect to Database. Exiting.")
        exit(1)
else:
    logger.info("Skipping database connectivity check for Testing Environment.")

# -------------------------------------------------
# 2. REDIS CONNECTION
# -------------------------------------------------
_redis_client = None

def get_redis():
    global _redis_client
    if _redis_client is None:
        host = os.getenv("REDIS_HOST", "redis-master") # Default to 'redis-master' for Kubernetes, fallback to localhost
        _redis_client = redis.StrictRedis(
            host=host, 
            port=6379, 
            decode_responses=True,
            socket_timeout=5
        )
    return _redis_client

# -------------------------------------------------
# 3. DB UPDATE HELPER
# -------------------------------------------------
def update_db_job(job_id: str, status: models.JobStatus, transcript: str = None, error_message: str = None):
    """Safely updates the Postgres record and handles rollbacks on failure."""
    db = SessionLocal()
    try:
        job = db.query(models.TranscriptionJob).filter(models.TranscriptionJob.id == job_id).first()
        if job:
            job.status = status
            if transcript is not None:
                job.transcript = transcript
            if error_message is not None:
                job.error_message = error_message
            db.commit()
            logger.info(f"Successfully updated DB for Job {job_id} to {status.value}")
        else:
            logger.warning(f"Job {job_id} not found in database during update.")
    except Exception as e:
        db.rollback() # Prevents broken transactions from hanging
        logger.error(f"Database update failed for job {job_id}: {e}")
    finally:
        db.close()

# -------------------------------------------------
# 4. AI MODEL INITIALIZATION
# -------------------------------------------------
# Ensure the models directory exists for the unprivileged appuser
os.makedirs("/models", exist_ok=True)

if os.getenv("ENV") != "testing":
    logger.info("Loading Faster-Whisper model into memory...")
    # This will download the model to /models on the first run
    model = WhisperModel(
        "base",
        device="cpu",
        compute_type="int8",
        download_root="/models"
    )
    logger.info("Model loaded successfully.")
else:
    model = None

# -------------------------------------------------
# 5. CORE TRANSCRIPTION TASK (HYBRID S3/LOCAL)
# -------------------------------------------------
def transcribe(job_id: str, video_identifier: str):
    r = get_redis()
    local_processing_path = video_identifier
    is_s3 = video_identifier.startswith("s3://")
    
    try:
        logger.info(f"Starting job {job_id}. Source: {video_identifier}")
        update_db_job(job_id, models.JobStatus.PROCESSING)

        # ==========================================
        # PHASE 1: FETCH THE FILE
        # ==========================================
        if is_s3:
            r.set(f"stage:{job_id}", "Downloading massive file from AWS S3...")
            r.set(f"progress:{job_id}", 10)
            
            # Extract bucket and key: s3://my-bucket/my-file.mp4
            parsed = urlparse(video_identifier)
            bucket = parsed.netloc
            key = parsed.path.lstrip('/')
            
            # Create a safe, temporary local path to hold the S3 download
            ext = key.split('.')[-1]
            local_processing_path = f"/tmp/{job_id}.{ext}"
            
            logger.info(f"Downloading {key} from bucket {bucket} to {local_processing_path}...")
            try:
                s3_client.download_file(bucket, key, local_processing_path)
            except Exception as e:
                raise RuntimeError(f"S3 download failed: {e}")
            
        else:
            r.set(f"stage:{job_id}", "Locating local file...")
            r.set(f"progress:{job_id}", 10)
            if not os.path.exists(local_processing_path):
                raise FileNotFoundError(f"Local file not found: {local_processing_path}")

        # ==========================================
        # PHASE 2: AI TRANSCRIPTION
        # ==========================================
        r.set(f"progress:{job_id}", 30)
        r.set(f"stage:{job_id}", "Transcribing audio...")

        segments, info = model.transcribe(local_processing_path, beam_size=5)
        
        transcription_text = ""
        for segment in segments:
            transcription_text += segment.text + " "

        full_transcript = transcription_text.strip()

        # ==========================================
        # PHASE 3: SAVE TO POSTGRES
        # ==========================================
        r.set(f"stage:{job_id}", "Saving results to Database...")
        r.set(f"progress:{job_id}", 95)
        
        update_db_job(job_id, models.JobStatus.COMPLETED, transcript=full_transcript)
        
        r.set(f"progress:{job_id}", 100)
        r.set(f"stage:{job_id}", "Complete")
        
        return full_transcript

    except Exception as e:
        logger.error(f"Error during transcription: {e}")
        update_db_job(job_id, models.JobStatus.FAILED, error_message=str(e))
        r.set(f"stage:{job_id}", "Failed")
        raise e
        
    finally:
        # ==========================================
        # PHASE 4: CLEANUP (CRITICAL DEVOPS STEP)
        # ==========================================
        # ONLY delete if it was downloaded from S3 to a temporary folder!
        if is_s3 and os.path.exists(local_processing_path):
            os.remove(local_processing_path)
            logger.info(f"Cleaned up temporary S3 download: {local_processing_path}")