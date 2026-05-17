from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

# Load PostgreSQL URL from .env
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

# Engine initialization with safeguard for missing URL
if SQLALCHEMY_DATABASE_URL:
    # Use pool_pre_ping to handle stale connections in serverless (Supabase/Vercel)
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        pool_recycle=300
    )
else:
    # Placeholder for local dev if URL is missing, or handles Vercel cold starts without ENV
    print("Warning: DATABASE_URL is not defined in environment variables.")
    # Use in-memory SQLite for module import stability if URL is missing
    engine = create_engine("sqlite://") 
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
