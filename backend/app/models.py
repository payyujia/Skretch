import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Float, DateTime, ForeignKey, JSON, Text, Integer
from sqlalchemy.orm import relationship

from .database import Base


def gen_id() -> str:
    return uuid.uuid4().hex[:12]


def now() -> datetime:
    return datetime.now(timezone.utc)


# Node types and the shape of their `data` payload (all optional/sparse):
#   sticky — data = {color, reactions, citations?: [{title, url}], source?: {doc_name, chunk_index}}
#   image  — data = {url, width, height}
#   frame  — data = {color, width, height}; `content` holds the frame's label.
#             Other nodes join it by setting `parent_id` to this node's id.
#             Frames are never themselves nested (parent_id stays null on a frame).
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
    )


class Board(Base):
    """Per-board metadata — currently holds the rolling AI summary used as
    persistent memory across chat sessions."""
    __tablename__ = "boards"

    id = Column(String, primary_key=True, default=gen_id)
    board_id = Column(String, unique=True, index=True, nullable=False)
    summary = Column(Text, default="")
    updated_at = Column(DateTime, default=now, onupdate=now)


class DocumentChunk(Base):
    """A chunk of text from a user-uploaded project document, stored with its
    embedding for RAG retrieval. The pgvector extension must be enabled on the
    PostgreSQL database."""
    __tablename__ = "document_chunks"

    id = Column(String, primary_key=True, default=gen_id)
    board_id = Column(String, index=True, nullable=False)
    doc_name = Column(String, nullable=False)   # original filename
    chunk_index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    # The embedding column uses pgvector's Vector type (768 dims for gemini-embedding-001).
    # We store it as JSON as a fallback when pgvector is not available; the vector_search
    # function handles both cases.
    embedding_json = Column(JSON, nullable=True)  # fallback storage
    created_at = Column(DateTime, default=now)
