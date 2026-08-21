import enum
from datetime import datetime
from sqlalchemy import String, Integer, ForeignKey, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from api.database import Base


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String, unique=True, index=True)
    installation_id: Mapped[str] = mapped_column(String)

    jobs: Mapped[list["Job"]] = relationship(back_populates="repository")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    repo: Mapped[str] = mapped_column(String, index=True)
    commit_sha: Mapped[str] = mapped_column(String, index=True)
    pull_number: Mapped[int] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String, default=JobStatus.PENDING.value)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    repository_id: Mapped[int] = mapped_column(ForeignKey("repositories.id"), nullable=True)
    repository: Mapped["Repository"] = relationship(back_populates="jobs")

    findings: Mapped[list["Finding"]] = relationship(back_populates="job", cascade="all, delete-orphan")


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    type: Mapped[str] = mapped_column(String)
    severity: Mapped[str] = mapped_column(String, index=True)
    file: Mapped[str] = mapped_column(String, index=True)
    line: Mapped[int] = mapped_column(Integer, nullable=True)
    message: Mapped[str] = mapped_column(Text)
    suggestion: Mapped[str] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String)

    job: Mapped["Job"] = relationship(back_populates="findings")