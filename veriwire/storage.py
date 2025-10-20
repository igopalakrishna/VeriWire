from datetime import datetime, UTC
from typing import Optional

from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker

engine = create_engine("sqlite:///veriwire.db", echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class CallSession(Base):
    __tablename__ = "call_sessions"
    id = Column(Integer, primary_key=True)
    streamsid = Column(String, index=True, unique=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))


class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True)
    streamsid = Column(String, index=True)
    kind = Column(String, index=True)
    data = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))


def init_db():
    Base.metadata.create_all(bind=engine)


def log_event(streamsid: str, kind: str, data: Optional[str] = None) -> None:
    with SessionLocal() as db:
        evt = Event(streamsid=streamsid, kind=kind, data=data or "")
        db.add(evt)
        db.commit()


