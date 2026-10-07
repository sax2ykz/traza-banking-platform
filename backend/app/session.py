"""SQLAlchemy sessions: one DB transaction context per request."""
from collections.abc import Generator

from sqlalchemy.orm import Session, sessionmaker

from app.database import engine

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session
