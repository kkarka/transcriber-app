import os
import time
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import OperationalError

# Configure logging to see the retry attempts in your Docker/K8s logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pulls from the environment variable set in docker-compose or kubernetes
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://kiran:password123@localhost:5432/transcription_db"
)

# Configuration for stability
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Checks connection health before every request
    pool_recycle=3600    # Prevents "stale" connections from sitting open too long
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def wait_for_db(retries=10, interval=3):
    """
    Pauses execution until the database is ready to accept connections.
    """
    logger.info("Checking database connectivity...")
    for i in range(retries):
        try:
            # Attempt a simple 'SELECT 1' to verify the connection
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            logger.info("Successfully connected to the database!")
            return True
        except (OperationalError, Exception) as e:
            logger.warning(f"Database not ready... (Attempt {i+1}/{retries}). Error: {e}")
            time.sleep(interval)
    
    logger.error("Could not connect to the database after multiple retries.")
    return False

# Dependency to get the DB session in your FastAPI routes
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()