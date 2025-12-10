from logging.config import fileConfig
import os

from sqlalchemy import engine_from_config, text, pool
from alembic import context

from database import Base, DATABASE_SCHEMA 
from authentication.models import *
from chat.models import *
from compliance.models import *  
from dotenv import load_dotenv
load_dotenv()


config = context.config


db_url = os.getenv("DATABASE_URL")
if db_url:
    db_url = db_url.replace("+asyncpg", "+psycopg2")
    config.set_main_option("sqlalchemy.url", db_url.replace('%', '%%'))


if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


# ---------------------------
# FILTER OBJECTS BY SCHEMA
# ---------------------------
def include_object(object, name, type_, reflected, compare_to):

    if type_ == "schema":
        return name == DATABASE_SCHEMA

    if reflected:
        if hasattr(object, "table") and object.table is not None:
            return object.table.schema == DATABASE_SCHEMA

        if hasattr(object, "schema"):
            return object.schema == DATABASE_SCHEMA

        return False

    return True


# ---------------------------
# OFFLINE MODE
# ---------------------------
def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        include_schemas=True,
        include_object=include_object,
        version_table_schema=DATABASE_SCHEMA,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


# ---------------------------
# ONLINE MODE
# ---------------------------
def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.begin() as connection:

        connection.execute(text(f"SET search_path TO {DATABASE_SCHEMA}, public"))

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            include_object=include_object,
            version_table_schema=DATABASE_SCHEMA,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
