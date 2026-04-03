import os
import time
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import OperationalError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -------------------------------------------------
# HYBRID CONFIG (LOCAL + DEV + PROD SAFE)
# -------------------------------------------------

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    logger.info("Using DATABASE_URL from environment")
else:
    logger.info("Using local DB configuration")

    DB_USER = os.getenv("POSTGRES_USER", "kiran")
    DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_NAME = os.getenv("POSTGRES_DB", "transcription_db")

    DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:5432/{DB_NAME}"

# -------------------------------------------------
# ENGINE
# -------------------------------------------------

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def wait_for_db(retries=10, interval=3):
    logger.info("Checking database connectivity...")
    for i in range(retries):
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            logger.info("Successfully connected to the database!")
            return True
        except (OperationalError, Exception):
            logger.warning(f"Database not ready... (Attempt {i+1}/{retries})")
            time.sleep(interval)

    logger.error("Could not connect to database")
    return False

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()