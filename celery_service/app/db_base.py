# db_base.py
import os
from dotenv import load_dotenv
from sqlalchemy.orm import declarative_base
from sqlalchemy import MetaData

load_dotenv()

# Get schema from environment variable
DATABASE_SCHEMA = os.getenv("DATABASE_SCHEMA", "testghostagent")

Base = declarative_base(metadata=MetaData(schema=DATABASE_SCHEMA))