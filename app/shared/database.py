import os
import time
import logging
import boto3
from urllib.parse import quote_plus
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import OperationalError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
DB_USER = os.getenv("POSTGRES_USER", "kiran")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD")  # No default! We check this for IAM Auth
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("POSTGRES_DB", "transcription_db")
REGION = os.getenv("AWS_DEFAULT_REGION", "ap-south-1")

def get_db_password():
    """
    Returns the password if available, otherwise generates an AWS IAM Token.
    """
    if DB_PASSWORD:
        return quote_plus(DB_PASSWORD)
    
    # If no password is provided, we assume we are in EKS using IAM Auth
    try:
        logger.info("No password found. Attempting to generate AWS RDS IAM Token...")
        rds_client = boto3.client('rds', region_name=REGION)
        # Port is 5432 as defined in your networking/RDS setup
        token = rds_client.generate_db_auth_token(
            DBHostname=DB_HOST,
            Port=5432,
            DBUsername=DB_USER,
            Region=REGION
        )
        return token
    except Exception as e:
        logger.error(f"Failed to generate IAM token: {e}")
        # Fallback for local development if everything else fails
        return "password123" 

# Build the connection string dynamically using the helper
# We don't use DATABASE_URL env var here to ensure the token is fresh on restart
pwd = get_db_password()
DATABASE_URL = f"postgresql://{DB_USER}:{pwd}@{DB_HOST}:5432/{DB_NAME}"

# --- ENGINE SETUP ---
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def wait_for_db(retries=10, interval=3):
    """Pauses execution until the database is ready."""
    logger.info(f"Checking database connectivity at {DB_HOST}...")
    for i in range(retries):
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            logger.info("Successfully connected to the database!")
            return True
        except (OperationalError, Exception) as e:
            logger.warning(f"Database not ready... (Attempt {i+1}/{retries}).")
            time.sleep(interval)
    
    logger.error("Could not connect to the database after multiple retries.")
    return False

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()