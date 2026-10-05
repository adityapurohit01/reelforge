"""Database management and session helpers for SQLite using SQLModel."""
from pathlib import Path
from typing import Generator
from sqlmodel import Session, SQLModel, create_engine

# Database file location in the project root
DB_PATH = Path("reelforge.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

# Create SQLite engine with foreign keys enabled
engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)


def get_engine(db_url: str = DATABASE_URL):
    """Create or return an SQLite engine."""
    return create_engine(
        db_url,
        echo=False,
        connect_args={"check_same_thread": False},
    )


def init_db(target_engine=None) -> None:
    """Create all tables in SQLite database if they don't already exist."""
    SQLModel.metadata.create_all(target_engine or engine)


def get_session(target_engine=None) -> Generator[Session, None, None]:
    """Provide a transactional scope around a series of operations."""
    with Session(target_engine or engine) as session:
        yield session
