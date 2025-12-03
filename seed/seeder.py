import csv
import os
import sys
import ssl
from pathlib import Path

# Add parent directory to Python path to allow imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from authentication.models import *
from sqlalchemy import insert
from datetime import datetime
from dotenv import load_dotenv
from common.config import settings

load_dotenv()

BASE_PATH = Path(__file__).parent

# Create sync database connection for seeding
db_url = os.getenv("DATABASE_URL") or settings.DATABASE_URL

if not db_url:
    raise ValueError("DATABASE_URL environment variable is not set")

# Replace async driver with psycopg2 for sync operations
if "+asyncpg" in db_url:
    db_url = db_url.replace("+asyncpg", "+psycopg2")

# Handle SSL if needed
connect_args = {}
use_ssl = getattr(settings, "DB_SSL", "false").lower() == "true"
if use_ssl:
    ssl_context = ssl.create_default_context()
    connect_args = {"ssl": ssl_context}

# Create sync engine
engine = create_engine(
    db_url,
    echo=False,
    pool_pre_ping=True,
    connect_args=connect_args,
)

# Set search_path on each connection (works with pooled connections)
@event.listens_for(engine, "connect", insert=True)
def set_search_path(dbapi_conn, connection_record):
    """Set the search path to the ghostagent schema on each connection"""
    cursor = dbapi_conn.cursor()
    cursor.execute("SET search_path TO ghostagent, public")
    cursor.close()

# Create sync session factory
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def load_csv(filename: str):
    """Reads a CSV file and returns list of rows as dicts."""
    path = BASE_PATH / filename
    with open(path, newline='', encoding="utf-8") as f:
        return list(csv.DictReader(f))


def seed_roles(db: Session):
    roles = load_csv("roles.csv")
    for r in roles:
        if db.query(Role).filter_by(name=r["name"]).first():
            continue
        
        db.add(Role(
            id=int(r["id"]),
            name=r["name"],
            description=r.get("description")
        ))
    db.commit()
    print("✔ roles seeded")


def seed_permissions(db: Session):
    permissions = load_csv("permissions.csv")
    for p in permissions:
        if db.query(Permission).filter_by(code=p["code"]).first():
            continue
        
        db.add(Permission(
            id=int(p["id"]),
            code=p["code"],
            name=p["name"],
            description=p.get("description")
        ))
    db.commit()
    print("✔ permissions seeded")


def seed_role_permissions(db: Session):
    rows = load_csv("role_permissions.csv")
    for row in rows:
        role_id = int(row["role_id"])
        permission_id = int(row["permission_id"])
        
        # Use PostgreSQL's ON CONFLICT DO NOTHING syntax
        stmt = text("""
            INSERT INTO role_permissions (role_id, permission_id)
            VALUES (:role_id, :permission_id)
            ON CONFLICT DO NOTHING
        """)
        db.execute(stmt, {"role_id": role_id, "permission_id": permission_id})
    db.commit()
    print("✔ role_permissions seeded")


def seed_users(db: Session):
    users = load_csv("users.csv")
    for u in users:
        if db.query(User).filter_by(email=u["email"]).first():
            continue
        
        db.add(User(
            id=int(u["id"]),
            email=u["email"],
            first_name=u["first_name"],
            last_name=u["last_name"],
            password=u["password"],
            is_active=u["is_active"].lower() == "true",
            is_superuser=u["is_superuser"].lower() == "true",
            profile_photo=u.get("profile_photo"),
            created_at=datetime.fromisoformat(u["created_at"]),
            last_login=datetime.fromisoformat(u["last_login"]) if u["last_login"] else None
        ))
    db.commit()
    print("✔ users seeded")


def seed_user_roles(db: Session):
    rows = load_csv("user_roles.csv")
    for row in rows:
        user_id = int(row["user_id"])
        role_id = int(row["role_id"])
        
        # Use PostgreSQL's ON CONFLICT DO NOTHING syntax
        stmt = text("""
            INSERT INTO user_roles (user_id, role_id)
            VALUES (:user_id, :role_id)
            ON CONFLICT DO NOTHING
        """)
        db.execute(stmt, {"user_id": user_id, "role_id": role_id})
    db.commit()
    print("✔ user_roles seeded")


def seed_tokens(db: Session):
    tokens = load_csv("user_tokens.csv")
    for t in tokens:
        if db.query(UserToken).filter_by(refresh_token=t["refresh_token"]).first():
            continue
        
        db.add(UserToken(
            id=int(t["id"]),
            user_id=int(t["user_id"]),
            refresh_token=t["refresh_token"],
            access_token=t["access_token"],
            access_token_expiry=datetime.fromisoformat(t["access_token_expiry"]),
            is_revoked=t["is_revoked"].lower() == "true",
            created_at=datetime.fromisoformat(t["created_at"]) if t["created_at"] else None
        ))
    db.commit()
    print("✔ user_tokens seeded")


def run_seeder():
    db = SessionLocal()
    try:
        print("🌱 Seeding database...")

        seed_roles(db)
        seed_permissions(db)
        seed_role_permissions(db)
        seed_users(db)
        seed_user_roles(db)
        seed_tokens(db)

        print("🎉 Database seeding completed!")
    except Exception as e:
        db.rollback()
        print(f"❌ Error seeding database: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_seeder()
