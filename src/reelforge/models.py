"""SQLModel data definitions for ReelForge."""
from datetime import datetime, timezone
from typing import Optional
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Business(SQLModel, table=True):
    __tablename__ = "businesses"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    vertical: str = Field(index=True)
    city: str = Field(index=True)
    locale: str
    owner_name: str
    profile_json: str  # JSON-encoded BusinessProfile
    fingerprint_id: Optional[int] = Field(default=None, foreign_key="fingerprints.id")
    created_at: datetime = Field(default_factory=utc_now)


class Plan(SQLModel, table=True):
    __tablename__ = "plans"

    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: str = Field(index=True, unique=True)
    axis_tuple_json: str  # JSON representation of selected axes
    seed: int
    relaxations_json: str = Field(default="[]")  # List of relaxed constraints if any
    created_at: datetime = Field(default_factory=utc_now)


class Video(SQLModel, table=True):
    __tablename__ = "videos"

    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: str = Field(index=True, unique=True)
    business_id: int = Field(foreign_key="businesses.id")
    state: str = Field(default="PLANNED", index=True)
    script_json: Optional[str] = None
    audio_path: Optional[str] = None
    video_path: Optional[str] = None
    cover_path: Optional[str] = None
    duration_s: Optional[float] = None
    loudness_lufs: Optional[float] = None
    qc_report_json: Optional[str] = None
    caption: Optional[str] = None
    hashtags_json: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)


class Fingerprint(SQLModel, table=True):
    __tablename__ = "fingerprints"

    id: Optional[int] = Field(default=None, primary_key=True)
    script_embedding: Optional[bytes] = None  # Float vector bytes
    hook_embedding: Optional[bytes] = None    # Float vector bytes
    trigram_set: Optional[bytes] = None      # Pickled / serialized set of 3-grams
    axis_tuple_json: str                     # Serialized axis dict
    created_at: datetime = Field(default_factory=utc_now)


class Approval(SQLModel, table=True):
    __tablename__ = "approvals"

    id: Optional[int] = Field(default=None, primary_key=True)
    video_id: int = Field(foreign_key="videos.id", index=True)
    decision: str  # APPROVED, REJECTED, REGENERATE, EDIT
    decided_by: str
    decided_at: datetime = Field(default_factory=utc_now)
    note: Optional[str] = None


class PublishLog(SQLModel, table=True):
    __tablename__ = "publish_log"

    id: Optional[int] = Field(default=None, primary_key=True)
    video_id: int = Field(foreign_key="videos.id", index=True)
    container_id: Optional[str] = None
    media_id: Optional[str] = None
    permalink: Optional[str] = None
    status: str = Field(default="PENDING")  # PENDING, IN_PROGRESS, PUBLISHED, FAILED
    error: Optional[str] = None
    attempts: int = Field(default=0)
    published_at: Optional[datetime] = None


class Metric(SQLModel, table=True):
    __tablename__ = "metrics"

    id: Optional[int] = Field(default=None, primary_key=True)
    video_id: int = Field(foreign_key="videos.id", index=True)
    window: str  # 24h, 72h, 7d
    reach: int = Field(default=0)
    views: int = Field(default=0)
    likes: int = Field(default=0)
    comments: int = Field(default=0)
    saves: int = Field(default=0)
    shares: int = Field(default=0)
    avg_watch_time_s: float = Field(default=0.0)
    fetched_at: datetime = Field(default_factory=utc_now)


class BanditStat(SQLModel, table=True):
    __tablename__ = "bandit_stats"

    arm_key: str = Field(primary_key=True)  # e.g., "vertical:hair_salon" or composite
    alpha: float = Field(default=1.0)
    beta: float = Field(default=1.0)
    n: int = Field(default=0)
    updated_at: datetime = Field(default_factory=utc_now)


class Run(SQLModel, table=True):
    __tablename__ = "runs"

    run_id: str = Field(primary_key=True)
    state: str = Field(default="PLANNED", index=True)
    started_at: datetime = Field(default_factory=utc_now)
    finished_at: Optional[datetime] = None
    stage_timings_json: str = Field(default="{}")
    error: Optional[str] = None
