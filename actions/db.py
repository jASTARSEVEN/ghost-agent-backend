# actions/db.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")

if not SUPABASE_URL:
    raise ValueError("❌ SUPABASE_URL not found in .env")

# Create the SQLAlchemy engine
engine = create_engine(
    SUPABASE_URL,
    pool_pre_ping=True,
    connect_args={"sslmode": "require"}
)

# Session factory for ORM usage if needed
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
