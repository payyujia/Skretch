from typing import Optional, Any
from pydantic import BaseModel, ConfigDict


class NodeCreate(BaseModel):
    type: str = "sticky"
    content: str = ""
    data: dict[str, Any] = {}
    x: float
    y: float
    created_by: str = "user"
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
    nodes: list[NodeOut]


class ImageUploadOut(BaseModel):
    url: str