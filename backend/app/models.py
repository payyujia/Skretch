import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Float, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship

from .database import Base


def gen_id() -> str:
    return uuid.uuid4().hex[:12]


def now() -> datetime:
    return datetime.now(timezone.utc)


# Node types and the shape of their `data` payload (all optional/sparse — a
# node only fills in the keys its type uses):
#   sticky — data = {color:'yellow',reactions: { "👍": 2, "🔥": 1 }
#   image  —  data =
#   frame  — data = {color:'yellow'}; `content` holds the frame's label. Other nodes join it
#               by setting `parent_id` to this node's id. Frames are never
#               themselves nested (parent_id stays null on a frame).
class Node(Base):
    __tablename__ = "nodes"

    id = Column(String, primary_key=True, default=gen_id)
    board_id = Column(String, default="default", index=True)
    type = Column(String, default="sticky")
    content = Column(String, default="")
    data = Column(JSON, default=dict)
    x = Column(Float, default=0)
    y = Column(Float, default=0)
    created_by = Column(String, default="user")  # "user" | "agent"
    parent_id = Column(String, ForeignKey("nodes.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)

    children = relationship(
        "Node",
        backref="parent",
        remote_side=[id],
        # a frame's children are incidental content, not an ownership chain
        # worth cascading through the ORM — deletion is handled explicitly in
        # crud.py (reparent-or-delete children before deleting a frame).
    )