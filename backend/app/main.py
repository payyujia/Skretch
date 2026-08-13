import asyncio
import io
import json
import logging

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Depends, HTTPException, Query, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import crud, schemas, agent, ai_gateway
from .database import engine, Base, get_db

Base.metadata.create_all(bind=engine)
logger = logging.getLogger("canvas")

app = FastAPI(title="Canvas API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Board & Node REST endpoints ───────────────────────────────────────────────

@app.get("/api/board", response_model=schemas.BoardOut)
def read_board(db: Session = Depends(get_db)):
    nodes = crud.get_board(db)
    return {"nodes": nodes}


@app.post("/api/nodes", response_model=schemas.NodeOut)
def create_node(payload: schemas.NodeCreate, db: Session = Depends(get_db)):
    return crud.create_node(
        db, content=payload.content, x=payload.x, y=payload.y,
        created_by=payload.created_by, type=payload.type, data=payload.data,
        parent_id=payload.parent_id,
    )


@app.patch("/api/nodes/{node_id}", response_model=schemas.NodeOut)
def update_node(node_id: str, payload: schemas.NodeUpdate, db: Session = Depends(get_db)):
    fields = payload.model_dump(exclude_none=True, exclude={"set_parent_id"})
    node = crud.update_node(db, node_id, set_parent_id=payload.set_parent_id, **fields)
    if not node:
        raise HTTPException(status_code=404, detail="node not found")
    return node


@app.delete("/api/nodes/{node_id}")
def delete_node(node_id: str, db: Session = Depends(get_db)):
    crud.delete_node(db, node_id)
    return {"status": "ok"}


# ── Document / RAG endpoints ──────────────────────────────────────────────────

def _parse_document(content: bytes, filename: str) -> list[str]:
    """Parse a document into a list of text chunks (300–600 chars each)."""
    ext = filename.rsplit(".", 1)[-1].lower()

    if ext == "pdf":
        try:
            import pypdf  # type: ignore
            reader = pypdf.PdfReader(io.BytesIO(content))
            full_text = "\n".join(
                page.extract_text() or "" for page in reader.pages
            )
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"PDF parsing failed: {e}")

    elif ext in ("docx", "doc"):
        try:
            import docx  # type: ignore
            doc = docx.Document(io.BytesIO(content))
            full_text = "\n".join(p.text for p in doc.paragraphs)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"DOCX parsing failed: {e}")

    elif ext == "txt":
        full_text = content.decode("utf-8", errors="replace")

    else:
        raise HTTPException(status_code=422, detail=f"Unsupported file type: .{ext}")

    # Chunk: split on double-newlines, then re-merge until 400 chars
    paragraphs = [p.strip() for p in full_text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        if not current:
            current = para
        elif len(current) + len(para) + 2 < 500:
            current += "\n\n" + para
        else:
            chunks.append(current)
            current = para
    if current:
        chunks.append(current)

    return chunks


@app.post("/api/documents", response_model=schemas.DocumentUploadOut)
async def upload_document(
    file: UploadFile = File(...),
    board_id: str = Form(default="default"),
    db: Session = Depends(get_db),
):
    content = await file.read()
    doc_name = file.filename or "document.txt"
    chunks = _parse_document(content, doc_name)

    if not chunks:
        raise HTTPException(status_code=422, detail="Document is empty or could not be parsed.")

    texts = chunks
    try:
        embeddings = await ai_gateway.embed_text(texts)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Embedding failed: {e}")

    crud.store_chunks(db, board_id=board_id, doc_name=doc_name, chunks=chunks, embeddings=embeddings)

    return {"doc_name": doc_name, "chunk_count": len(chunks), "board_id": board_id}


@app.get("/api/documents")
def list_documents(board_id: str = Query(default="default"), db: Session = Depends(get_db)):
    doc_names = crud.list_documents(db, board_id=board_id)
    return {"documents": doc_names, "board_id": board_id}


@app.delete("/api/documents/{doc_name}")
def delete_document(
    doc_name: str,
    board_id: str = Query(default="default"),
    db: Session = Depends(get_db),
):
    n = crud.delete_document(db, board_id=board_id, doc_name=doc_name)
    if n == 0:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"status": "ok", "deleted_chunks": n}


# ── WebSocket chat ────────────────────────────────────────────────────────────

@app.websocket("/ws/chat")
async def chat_ws(ws: WebSocket, board_id: str = Query(default="default")):
    """One user message in, a stream of {type: ...} events out:
    node_thinking, node_added, node_updated, node_deleted, token, message_done, error."""
    await ws.accept()
    db = next(get_db())
    history: list[dict] = []

    async def send(event: dict) -> None:
        await ws.send_text(json.dumps(event))

    try:
        while True:
            raw = await ws.receive_text()
            payload = json.loads(raw)
            user_message = payload.get("content", "").strip()
            if not user_message:
                continue

            attached_doc_names: list[str] = payload.get("attached_doc_names", []) or []
            board_summary = crud.get_board_summary(db, board_id)

            try:
                reply = await agent.run_agent_turn(
                    db,
                    user_message,
                    history,
                    send,
                    board_id=board_id,
                    attached_doc_names=attached_doc_names or None,
                    board_summary=board_summary,
                )
            except RuntimeError as e:
                logger.warning("agent turn failed: %s", e)
                await send({"type": "error", "message": str(e)})
                continue
            except Exception:
                logger.exception("agent turn failed")
                await send({"type": "error", "message": "The agent hit an unexpected error."})
                continue

            history.append({"role": "user", "content": user_message})
            if reply:
                history.append({"role": "assistant", "content": reply})
            del history[:-12]  # keep window small; board snapshot carries real state

            # Fire-and-forget board summary update after each turn
            asyncio.create_task(
                ai_gateway.update_board_summary(db, board_id, history)
            )

    except WebSocketDisconnect:
        pass
    finally:
        db.close()
