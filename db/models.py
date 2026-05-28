"""
LogPulse — Database Layer
SQLAlchemy async engine, models, and session management.
Tables: logs, anomalies
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Text, Boolean
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from config import settings

Base = declarative_base()

engine = create_async_engine(settings.database_url, echo=False)

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class LogEntry(Base):
    """Stores every ingested log line."""
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    level = Column(String(10), index=True)       # INFO | WARN | ERROR | CRITICAL
    service = Column(String(64), index=True)
    message = Column(Text)
    raw = Column(Text)                           # original raw log string


class Anomaly(Base):
    """Stores detected anomalies with LLM enrichment."""
    __tablename__ = "anomalies"

    id = Column(Integer, primary_key=True, index=True)
    detected_at = Column(DateTime, default=datetime.utcnow, index=True)
    service = Column(String(64))
    error_rate = Column(Float)                   # error rate at detection time
    zscore = Column(Float)                       # Z-score that triggered detection
    window_size = Column(Integer)                # sliding window size used
    error_count = Column(Integer)                # errors in window
    total_count = Column(Integer)                # total logs in window
    llm_root_cause = Column(Text, nullable=True) # LLM root cause hypothesis
    llm_severity = Column(String(16), nullable=True)  # LOW | MEDIUM | HIGH | CRITICAL
    llm_suggested_action = Column(Text, nullable=True)
    llm_provider_used = Column(String(16), nullable=True)  # ollama | openai
    webhook_fired = Column(Boolean, default=False)
    webhook_status = Column(String(16), nullable=True)     # success | failed


async def init_db():
    """Create all tables if they don't exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    """Dependency-injectable async DB session."""
    async with AsyncSessionLocal() as session:
        yield session
