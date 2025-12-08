# from logging.config import fileConfig
# import os

# from sqlalchemy import engine_from_config, text
# from sqlalchemy import pool

# from alembic import context
# from database import Base
# from authentication.models import *
# from chat.models import *
# from compliance.models import *
# from dotenv import load_dotenv
# load_dotenv()

# # this is the Alembic Config object, which provides
# # access to the values within the .ini file in use.
# config = context.config

# # Override DB URL dynamically
# db_url = os.getenv("DATABASE_URL")

# if db_url:
#     # Replace async driver with psycopg2 for Alembic
#     db_url = db_url.replace("+asyncpg", "+psycopg2")
#     # Escape percent signs to avoid ConfigParser interpolation issues
#     safe_db_url = db_url.replace('%', '%%')
#     # Set directly from .env
#     config.set_main_option("sqlalchemy.url", safe_db_url)

# # Interpret the config file for Python logging.
# # This line sets up loggers basically.
# if config.config_file_name is not None:
#     fileConfig(config.config_file_name)

# # add your model's MetaData object here
# # for 'autogenerate' support
# # from myapp import mymodel
# # target_metadata = mymodel.Base.metadata
# # target_metadata = None
# target_metadata = Base.metadata

# # other values from the config, defined by the needs of env.py,
# # can be acquired:
# # my_important_option = config.get_main_option("my_important_option")
# # ... etc.


# def run_migrations_offline() -> None:
#     """Run migrations in 'offline' mode.

#     This configures the context with just a URL
#     and not an Engine, though an Engine is acceptable
#     here as well.  By skipping the Engine creation
#     we don't even need a DBAPI to be available.

#     Calls to context.execute() here emit the given string to the
#     script output.

#     """
#     url = config.get_main_option("sqlalchemy.url")
#     context.configure(
#         url=url,
#         target_metadata=target_metadata,
#         literal_binds=True,
#         dialect_opts={"paramstyle": "named"},
#         version_table_schema='testdb'
#     )

#     with context.begin_transaction():
#         context.run_migrations()


# def run_migrations_online() -> None:
#     """Run migrations in 'online' mode.

#     In this scenario we need to create an Engine
#     and associate a connection with the context.

#     """
#     connectable = engine_from_config(
#         config.get_section(config.config_ini_section, {}),
#         prefix="sqlalchemy.",
#         poolclass=pool.NullPool,
#     )

#     with connectable.connect() as connection:
#         # Set the search path to testdb schema
#         connection.execute(text("SET search_path TO testdb"))
#         connection.commit()
        
#         context.configure(
#             connection=connection, 
#             target_metadata=target_metadata,
#             version_table_schema='testdb'
#         )

#         with context.begin_transaction():
#             context.run_migrations()


# if context.is_offline_mode():
#     run_migrations_offline()
# else:
#     run_migrations_online()

#  verison 2----------------------------------------------------------------------------------------------

# from logging.config import fileConfig
# import os

# from sqlalchemy import engine_from_config, text
# from sqlalchemy import pool

# from alembic import context
# from database import Base
# from authentication.models import *
# from chat.models import *
# from compliance.models import *
# from dotenv import load_dotenv
# load_dotenv()

# # this is the Alembic Config object, which provides
# # access to the values within the .ini file in use.
# config = context.config

# # Override DB URL dynamically
# db_url = os.getenv("DATABASE_URL")

# if db_url:
#     # Replace async driver with psycopg2 for Alembic
#     db_url = db_url.replace("+asyncpg", "+psycopg2")
#     # Escape percent signs to avoid ConfigParser interpolation issues
#     safe_db_url = db_url.replace('%', '%%')
#     # Set directly from .env
#     config.set_main_option("sqlalchemy.url", safe_db_url)

# # Interpret the config file for Python logging.
# # This line sets up loggers basically.
# if config.config_file_name is not None:
#     fileConfig(config.config_file_name)

# # add your model's MetaData object here
# # for 'autogenerate' support
# # from myapp import mymodel
# # target_metadata = mymodel.Base.metadata
# # target_metadata = None
# target_metadata = Base.metadata

# # other values from the config, defined by the needs of env.py,
# # can be acquired:
# # my_important_option = config.get_main_option("my_important_option")
# # ... etc.

# def include_object(object, name, type_, reflected, compare_to):
#     """Filter to only include objects from the testdb schema."""
#     # Ignore schemas other than testdb
#     if type_ == "schema":
#         return name == "testdb"
    
#     # For reflected objects (from database), check their schema
#     if reflected:
#         if hasattr(object, "schema"):
#             schema = object.schema
#             if schema and schema != "testdb":
#                 return False
#         # For indexes, constraints, etc. that reference tables
#         if hasattr(object, "table") and hasattr(object.table, "schema"):
#             if object.table.schema and object.table.schema != "testdb":
#                 return False
    
#     # For model objects (from target_metadata), they should all be in testdb
#     # since Base.metadata has schema="testdb"
#     if not reflected:
#         return True
    
#     # Default: include if schema is testdb or None (public schema, which we also ignore)
#     if hasattr(object, "schema"):
#         return object.schema == "testdb" if object.schema else False
    
#     return True


# def run_migrations_offline() -> None:
#     """Run migrations in 'offline' mode.

#     This configures the context with just a URL
#     and not an Engine, though an Engine is acceptable
#     here as well.  By skipping the Engine creation
#     we don't even need a DBAPI to be available.

#     Calls to context.execute() here emit the given string to the
#     script output.

#     """
#     url = config.get_main_option("sqlalchemy.url")
#     context.configure(
#         url=url,
#         target_metadata=target_metadata,
#         literal_binds=True,
#         dialect_opts={"paramstyle": "named"},
#         version_table_schema='testdb',
#         include_schemas=True,
#         include_object=include_object
#     )

#     with context.begin_transaction():
#         context.run_migrations()


# def run_migrations_online() -> None:
#     """Run migrations in 'online' mode.

#     In this scenario we need to create an Engine
#     and associate a connection with the context.

#     """
#     connectable = engine_from_config(
#         config.get_section(config.config_ini_section, {}),
#         prefix="sqlalchemy.",
#         poolclass=pool.NullPool,
#     )

#     with connectable.connect() as connection:
#         # Configure Alembic to properly handle schema-aware autogenerate
#         # Filter to only include objects from testdb schema
#         context.configure(
#             connection=connection, 
#             target_metadata=target_metadata,
#             version_table_schema='testdb',
#             include_schemas=True,
#             include_object=include_object
#         )

#         with context.begin_transaction():
#             context.run_migrations()


# if context.is_offline_mode():
#     run_migrations_offline()
# else:
#     run_migrations_online()


# version 3 ----------------------------------------------------------------------------------------------
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

    with connectable.connect() as connection:

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
