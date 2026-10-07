import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import URL, create_engine, text

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "127.0.0.1")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5433"))
POSTGRES_SSLMODE = os.getenv("POSTGRES_SSLMODE", "").strip()

query = {}

if POSTGRES_SSLMODE:
    query["sslmode"] = POSTGRES_SSLMODE

DATABASE_URL = URL.create(
    drivername="postgresql+psycopg",
    username=os.environ["POSTGRES_USER"],
    password=os.environ["POSTGRES_PASSWORD"],
    host=POSTGRES_HOST,
    port=POSTGRES_PORT,
    database=os.environ["POSTGRES_DB"],
    query=query,
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)


def check_database():
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return True
