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
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
else:
    # Placeholder for local dev if URL is missing, or handles Vercel cold starts without ENV
    print("Warning: DATABASE_URL is not defined in environment variables.")
    # Use a dummy SQLite for module import stability if needed, 
    # but the app will likely fail on DB dependency anyway.
    engine = create_engine("sqlite:///./fallback.db") 
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
