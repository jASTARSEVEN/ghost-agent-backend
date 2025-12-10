import os
from dotenv import load_dotenv
from sqlalchemy.orm import declarative_base
from sqlalchemy import MetaData

load_dotenv()

DATABASE_SCHEMA = os.getenv("DATABASE_SCHEMA", "testdb")

Base = declarative_base(metadata=MetaData(schema=DATABASE_SCHEMA))