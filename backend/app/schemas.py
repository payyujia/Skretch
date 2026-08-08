from typing import Optional
from pydantic import BaseModel, ConfigDict


class NodeCreate(BaseModel):
    content: str = ""
    x: float
    y: float
    created_by: str = "user"


class NodeUpdate(BaseModel):
    content: Optional[str] = None
    x: Optional[float] = None
    y: Optional[float] = None


class NodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    content: str
    x: float
    y: float
    created_by: str


class EdgeCreate(BaseModel):
    source_id: str
    target_id: str


class EdgeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    source_id: str
    target_id: str


class BoardOut(BaseModel):
    nodes: list[NodeOut]
    edges: list[EdgeOut]
