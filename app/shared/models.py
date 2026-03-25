import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Enum
from database import Base
import enum

class JobStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class TranscriptionJob(Base):
    __tablename__ = "transcription_jobs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    filename = Column(String, index=True)
    status = Column(Enum(JobStatus), default=JobStatus.PENDING)
    transcript = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)