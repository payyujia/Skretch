from typing import Optional, Any, Literal
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class NodeCreate(BaseModel):
    type: str = "sticky"
    content: str = ""
    data: dict[str, Any] = {}
    x: float
    y: float
    created_by: str
    parent_id: Optional[str] = None


class NodeUpdate(BaseModel):
    content: Optional[str] = None
    data: Optional[dict[str, Any]] = None
    x: Optional[float] = None
    y: Optional[float] = None
    # Distinct from "not provided": omit this field to leave parent unchanged,
    # or set it explicitly (including null) to move the node in/out of a frame.
    parent_id: Optional[str] = None
    set_parent_id: bool = False


class NodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    type: str
    content: str
    data: dict[str, Any]
    x: float
    y: float
    created_by: str
    parent_id: Optional[str] = None

class BoardOut(BaseModel):
    board_id: int
    name: str
    nodes: list[NodeOut]

class ImageUploadOut(BaseModel):
    url: str


class DocumentUploadOut(BaseModel):
    doc_name: str
    chunk_count: int
    board_id: int


# ── User ──────────────────────────────────────────────────────────────────────

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str
    name: str
    avatar_url: Optional[str] = None


# ── Board ─────────────────────────────────────────────────────────────────────

class BoardCreate(BaseModel):
    name: str = "Untitled Board"
    template: Literal["blank", "kanban", "okr", "retrospective"] = "blank"


class BoardDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    board_id: int
    name: str
    owner_id: Optional[str] = None
    last_visited_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class BoardListOut(BaseModel):
    boards: list[BoardDetail]


class ExportRequest(BaseModel):
    board_id: int
    payload: dict
    format: str = "auto"   # "essay" | "prd" | "auto"


class ExportResult(BaseModel):
    doc_url: str
    doc_id: str
    title: str