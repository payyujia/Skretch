import math
import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from . import models

logger = logging.getLogger("canvas.crud")

BOARD_ID = "default"  # single-board MVP; swap for a real id once multi-board lands


# ── Node CRUD ─────────────────────────────────────────────────────────────────

def get_board(db: Session, board_id: str = BOARD_ID):
    return db.query(models.Node).filter_by(board_id=board_id).all()


def get_node(db: Session, node_id: str):
    return db.get(models.Node, node_id)


def create_node(db: Session, content: str = "", x: float = 0, y: float = 0,
                 created_by: str = "user", type: str = "sticky", data: dict | None = None,
                 parent_id: str | None = None, board_id: str = BOARD_ID):
    node = models.Node(
        content=content, x=x, y=y, created_by=created_by,
        type=type, data=data or {}, parent_id=parent_id, board_id=board_id,
    )
    db.add(node)
    db.commit()
    db.refresh(node)
    return node


def update_node(db: Session, node_id: str, set_parent_id: bool = False, **fields):
    """`set_parent_id=True` is required to touch parent_id — that's the only
    field where "not provided" and "explicitly set to null" mean different
    things (leave the frame membership alone vs. pop the node out of its
    frame), so it can't use the same "skip if None" rule as every other field.
    """
    node = get_node(db, node_id)
    if not node:
        return None
    parent_id = fields.pop("parent_id", None)
    for key, value in fields.items():
        if value is not None:
            setattr(node, key, value)
    if set_parent_id:
        node.parent_id = parent_id
    db.commit()
    db.refresh(node)
    return node


def delete_node(db: Session, node_id: str) -> bool:
    node = get_node(db, node_id)
    if not node:
        return False
    # Deleting a frame shouldn't take its contents down with it — orphan any
    # children back to the top level instead of cascading the delete.
    db.query(models.Node).filter(models.Node.parent_id == node_id).update(
        {"parent_id": None}, synchronize_session=False
    )
    db.delete(node)
    db.commit()
    return True


# ── Board memory ──────────────────────────────────────────────────────────────

def get_board_summary(db: Session, board_id: str) -> str | None:
    row = db.query(models.Board).filter_by(board_id=board_id).first()
    return row.summary if row else None


def upsert_board_summary(db: Session, board_id: str, summary: str) -> None:
    row = db.query(models.Board).filter_by(board_id=board_id).first()
    if row:
        row.summary = summary
    else:
        row = models.Board(board_id=board_id, summary=summary)
        db.add(row)
    db.commit()


def get_board_snapshot_text(db: Session, board_id: str = BOARD_ID) -> str:
    """Plain-text board snapshot used by the summary generator."""
    nodes = db.query(models.Node).filter_by(board_id=board_id).all()
    if not nodes:
        return "Empty board."
    lines = []
    frames = {n.id: n for n in nodes if n.type == "frame"}
    for f in frames.values():
        lines.append(f'Frame: "{f.content}"')
        children = [n for n in nodes if n.parent_id == f.id]
        for c in children:
            lines.append(f'  - {c.type}: "{c.content}"')
    ungrouped = [n for n in nodes if n.parent_id is None and n.type != "frame"]
    if ungrouped:
        lines.append("Ungrouped:")
        for n in ungrouped:
            lines.append(f'  - {n.type}: "{n.content}"')
    return "\n".join(lines)


# ── Document chunk storage ────────────────────────────────────────────────────

def store_chunks(
    db: Session,
    board_id: str,
    doc_name: str,
    chunks: list[str],
    embeddings: list[list[float]],
) -> list[models.DocumentChunk]:
    """Persist text chunks with their embeddings. Replaces any existing chunks
    for the same (board_id, doc_name) pair to support re-uploads."""
    # Delete old chunks for this doc on this board
    db.query(models.DocumentChunk).filter_by(
        board_id=board_id, doc_name=doc_name
    ).delete(synchronize_session=False)
    db.flush()

    rows = []
    for idx, (text, emb) in enumerate(zip(chunks, embeddings)):
        row = models.DocumentChunk(
            board_id=board_id,
            doc_name=doc_name,
            chunk_index=idx,
            text=text,
            embedding_json=emb,
        )
        rows.append(row)
        db.add(row)

    db.commit()
    return rows


def list_documents(db: Session, board_id: str) -> list[str]:
    """Return a deduplicated list of doc_names uploaded to this board."""
    rows = (
        db.query(models.DocumentChunk.doc_name)
        .filter_by(board_id=board_id)
        .distinct()
        .all()
    )
    return [r.doc_name for r in rows]


def delete_document(db: Session, board_id: str, doc_name: str) -> int:
    """Delete all chunks for a document. Returns number of rows deleted."""
    n = db.query(models.DocumentChunk).filter_by(
        board_id=board_id, doc_name=doc_name
    ).delete(synchronize_session=False)
    db.commit()
    return n


def vector_search(
    db: Session,
    board_id: str,
    query_embedding: list[float],
    top_k: int = 5,
    doc_names: list[str] | None = None,
) -> list[models.DocumentChunk]:
    """Cosine similarity search over document chunks for a board.

    Strategy: we store embeddings as JSON arrays in `embedding_json`.
    We compute cosine similarity in Python — acceptable for MVP scale
    (< 10k chunks per board). When pgvector is enabled in a future migration,
    swap this body for a native `<=>` SQL query.
    """
    query = db.query(models.DocumentChunk).filter_by(board_id=board_id)
    if doc_names:
        query = query.filter(models.DocumentChunk.doc_name.in_(doc_names))
    chunks = query.all()

    if not chunks:
        return []

    q = query_embedding
    q_norm = math.sqrt(sum(v * v for v in q)) or 1.0

    scored: list[tuple[float, models.DocumentChunk]] = []
    for chunk in chunks:
        emb = chunk.embedding_json
        if not emb:
            continue
        dot = sum(a * b for a, b in zip(q, emb))
        e_norm = math.sqrt(sum(v * v for v in emb)) or 1.0
        sim = dot / (q_norm * e_norm)
        scored.append((sim, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:top_k]]
