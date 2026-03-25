import os
import logging
import redis
import uuid
import yt_dlp
from rq import get_current_job
from faster_whisper import WhisperModel

# Import your database and models
# Ensure your PYTHONPATH includes /shared and /app
from database import SessionLocal, wait_for_db, engine
import models 

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
        host = os.getenv("REDIS_HOST", "redis")
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
    # This will download the model to /models on the first run
    model = WhisperModel(
        "base",
        device="cpu",
        compute_type="int8",
        download_root="/models"
    )
else:
    model = None

# -------------------------------------------------
# 5. CORE TRANSCRIPTION TASK
# -------------------------------------------------
def transcribe(job_id: str, video_path: str):
    r = get_redis()
    
    try:
        logger.info(f"Starting transcription for Job {job_id}: {video_path}")
        update_db_job(job_id, models.JobStatus.PROCESSING)

        r.set(f"progress:{job_id}", 10)
        r.set(f"stage:{job_id}", "Transcribing audio...")

        segments, info = model.transcribe(video_path)
        total_duration = info.duration

        transcript_parts = []
        for segment in segments:
            transcript_parts.append(segment.text)
            
            # Real-time progress update to Redis for the Frontend
            percent = int((segment.end / total_duration) * 100)
            mapped_percent = 10 + int((percent / 100) * 85)
            r.set(f"progress:{job_id}", min(mapped_percent, 95))
            r.set(f"stage:{job_id}", "Extracting text...")

        full_transcript = " ".join(transcript_parts).strip()
        
        # Save the final transcript to Postgres FIRST
        update_db_job(job_id, models.JobStatus.COMPLETED, transcript=full_transcript)
        logger.info(f"Job {job_id} completed successfully.")
        
        # Finalize
        r.set(f"progress:{job_id}", 100)
        r.set(f"stage:{job_id}", "Complete")
        
        return full_transcript

    except Exception as e:
        logger.error(f"Transcription error for {job_id}: {e}")
        update_db_job(job_id, models.JobStatus.FAILED, error_message=str(e))
        r.set(f"stage:{job_id}", f"Error: {str(e)}")
        raise e
    finally:
        if os.path.exists(video_path):
            os.remove(video_path)

# -------------------------------------------------
# 6. YOUTUBE TASK
# -------------------------------------------------
def transcribe_youtube_job(job_id: str, youtube_url: str):
    r = get_redis()
    temp_id = str(uuid.uuid4())
    output_tmpl = os.path.join("/app/uploads", f"{temp_id}.%(ext)s")

    try:
        update_db_job(job_id, models.JobStatus.PROCESSING)
        r.set(f"progress:{job_id}", 5)
        r.set(f"stage:{job_id}", "Downloading from YouTube...")

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": output_tmpl,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "192"
            }],
            "quiet": True
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([youtube_url])

        audio_path = output_tmpl.replace("%(ext)s", "wav")
        return transcribe(job_id, audio_path)

    except Exception as e:
        logger.error(f"YouTube job failed: {e}")
        update_db_job(job_id, models.JobStatus.FAILED, error_message=f"YouTube Error: {str(e)}")
        r.set(f"stage:{job_id}", "Download failed")
        raise e