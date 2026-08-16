import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Float, DateTime, ForeignKey, JSON, Text, Integer, Table
from sqlalchemy.orm import relationship

from .database import Base


def gen_id() -> str:
    return uuid.uuid4().hex[:12]


def now() -> datetime:
    return datetime.now(timezone.utc)


# ── M2M: board ↔ collaborating users ─────────────────────────────────────────
board_collaborators = Table(
    "board_collaborators",
    Base.metadata,
    Column("board_id", Integer, ForeignKey("boards.board_id", ondelete="CASCADE"), primary_key=True),
    Column("user_id",  String, ForeignKey("users.id",  ondelete="CASCADE"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id         = Column(String, primary_key=True, default=gen_id)
    google_id  = Column(String, unique=True, index=True, nullable=True)
    email      = Column(String, unique=True, nullable=False)
    name       = Column(String, default="")
    avatar_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=now)

    # Google OAuth tokens — stored for Drive/Docs API calls on behalf of the user
    google_access_token  = Column(Text, nullable=True)
    google_refresh_token = Column(Text, nullable=True)
    google_token_expiry  = Column(Float, nullable=True)  # Unix timestamp

    owned_boards = relationship("Board", back_populates="owner", foreign_keys="Board.owner_id")


# Node types and the shape of their `data` payload (all optional/sparse):
#   sticky — data = {color, reactions, citations?: [{title, url}], source?: {doc_name, chunk_index}}
#   image  — data = {url, width, height}
#   frame  — data = {color, width, height}; `content` holds the frame's label.
#             Other nodes join it by setting `parent_id` to this node's id.
#             Frames are never themselves nested (parent_id stays null on a frame).
class Node(Base):
    __tablename__ = "nodes"

    id = Column(String, primary_key=True, default=gen_id)
    board_id = Column(Integer, ForeignKey("boards.board_id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String, default="sticky")
    content = Column(String, default="")
    data = Column(JSON, default=dict)
    x = Column(Float, default=0)
    y = Column(Float, default=0)
    created_by = Column(String, default="user")
    parent_id = Column(String, ForeignKey("nodes.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)

    children = relationship(
        "Node",
        backref="parent",
        remote_side=[id],
    )


class Board(Base):
    """Per-board entity — holds identity, ownership, AI summary, and collaborators."""
    __tablename__ = "boards"

    board_id        = Column(Integer, primary_key=True)
    name            = Column(String, default="Untitled Board")
    owner_id        = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    last_visited_at = Column(DateTime, nullable=True)
    summary         = Column(Text, default="")
    updated_at      = Column(DateTime, default=now, onupdate=now)
    created_at      = Column(DateTime, default=now)

    owner         = relationship("User", back_populates="owned_boards", foreign_keys=[owner_id])
    collaborators = relationship("User", secondary=board_collaborators)


class DocumentChunk(Base):
    """A chunk of text from a user-uploaded project document, stored with its
    embedding for RAG retrieval. The pgvector extension must be enabled on the
    PostgreSQL database."""
    __tablename__ = "document_chunks"

    id = Column(String, primary_key=True, default=gen_id)
    board_id = Column(Integer, ForeignKey("boards.board_id", ondelete="CASCADE"), index=True, nullable=False)
    doc_name = Column(String, nullable=False)   # original filename
    chunk_index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    # The embedding column uses pgvector's Vector type (768 dims for gemini-embedding-001).
    # We store it as JSON as a fallback when pgvector is not available; the vector_search
    # function handles both cases.
    embedding_json = Column(JSON, nullable=True)  # fallback storage
    created_at = Column(DateTime, default=now)
