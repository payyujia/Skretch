import json
import logging

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import crud, schemas, agent
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


@app.websocket("/ws/chat")
async def chat_ws(ws: WebSocket):
    """One user message in, a stream of {type: ...} events out: node_thinking,
    node_added, node_updated, node_deleted, token, message_done, error."""
    await ws.accept()
    db = next(get_db())
    history: list[dict] = []

    async def send(event: dict) -> None:
        await ws.send_text(json.dumps(event))

    try:
        while True:
            raw = await ws.receive_text()
            user_message = json.loads(raw).get("content", "").strip()
            if not user_message:
                continue

            try:
                reply = await agent.run_agent_turn(db, user_message, history, send)
            except RuntimeError as e:  # missing key, quota exhausted, rate-limited after retries, etc.
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
            del history[:-12]  # keep the window small; the board snapshot carries real state
    except WebSocketDisconnect:
        pass
    finally:
        db.close()