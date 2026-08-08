import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Float, DateTime, ForeignKey

from .database import Base


def gen_id() -> str:
    return uuid.uuid4().hex[:12]


def now() -> datetime:
    return datetime.now(timezone.utc)


class Node(Base):
    __tablename__ = "nodes"

    id = Column(String, primary_key=True, default=gen_id)
    board_id = Column(String, default="default", index=True)
    content = Column(String, default="")
    x = Column(Float, default=0)
    y = Column(Float, default=0)
    created_by = Column(String, default="user")  # "user" | "agent"
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class Edge(Base):
    __tablename__ = "edges"

    id = Column(String, primary_key=True, default=gen_id)
    board_id = Column(String, default="default", index=True)
    source_id = Column(String, ForeignKey("nodes.id"))
    target_id = Column(String, ForeignKey("nodes.id"))
    created_at = Column(DateTime, default=now)
