# db_base.py
import os
from dotenv import load_dotenv
from sqlalchemy.orm import declarative_base
from sqlalchemy import MetaData

load_dotenv()

# Get schema from environment variable, default to "testdb"
DATABASE_SCHEMA = os.getenv("DATABASE_SCHEMA", "testdb")

Base = declarative_base(metadata=MetaData(schema=DATABASE_SCHEMA))