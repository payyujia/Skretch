import asyncio
import io
import json
import logging
import time
from collections import defaultdict
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Depends, HTTPException, Query, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from . import crud, schemas, agent, ai_gateway, auth as auth_module, export as export_module
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


# ── Google OAuth ──────────────────────────────────────────────────────────────

@app.get("/api/auth/google")
async def auth_google():
    """Redirect the browser to Google's OAuth consent screen."""
    url = auth_module.build_google_auth_url()
    return RedirectResponse(url)


@app.get("/api/auth/google/callback")
async def auth_callback(code: str, db: Session = Depends(get_db)):
    """Handle the OAuth callback, upsert user, issue JWT, redirect to frontend."""
    try:
        tokens = await auth_module.exchange_code(code)
    except Exception as exc:
        logger.warning("OAuth code exchange failed: %s", exc)
        raise HTTPException(status_code=400, detail="OAuth code exchange failed")

    try:
        userinfo = await auth_module.get_google_userinfo(tokens["access_token"])
    except Exception as exc:
        logger.warning("Failed to fetch Google userinfo: %s", exc)
        raise HTTPException(status_code=400, detail="Failed to fetch Google user info")

    user = crud.upsert_user(
        db,
        google_id=userinfo["id"],
        email=userinfo.get("email", ""),
        name=userinfo.get("name", ""),
        avatar_url=userinfo.get("picture"),
        access_token=tokens.get("access_token"),
        refresh_token=tokens.get("refresh_token"),
        token_expiry=time.time() + tokens.get("expires_in", 3600),
    )

    jwt_token = auth_module.create_jwt(user.id, user.email, name=user.name, avatar_url=user.avatar_url)
    frontend_url = auth_module.FRONTEND_URL
    return RedirectResponse(f"{frontend_url}/?token={jwt_token}")


@app.get("/api/auth/me", response_model=schemas.UserOut)
def auth_me(current_user=Depends(auth_module.require_user)):
    """Return the currently authenticated user's profile."""
    return current_user


# ── Export ────────────────────────────────────────────────────────────────────

@app.post("/api/export/docs", response_model=schemas.ExportResult)
async def export_to_google_docs(
    req: schemas.ExportRequest,
    current_user=Depends(auth_module.require_user),
    db: Session = Depends(get_db),
):
    """Generate an AI-authored document from the board and create it in Google Docs."""
    try:
        result = await export_module.export_board_to_docs(
            user=current_user,
            db=db,
            board_id=req.board_id,
            payload=req.payload,
            fmt_hint=req.format,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("Export failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Export failed: {exc}")
    return result


# ── Boards REST API ───────────────────────────────────────────────────────────

@app.get("/api/boards", response_model=schemas.BoardListOut)
def list_boards(current_user=Depends(auth_module.require_user), db: Session = Depends(get_db)):
    """Return all boards the authenticated user owns or collaborates on."""
    boards = crud.get_user_boards(db, current_user.id)
    return {"boards": boards}


@app.post("/api/boards", response_model=schemas.BoardDetail)
def create_board(
    payload: schemas.BoardCreate,
    current_user=Depends(auth_module.require_user),
    db: Session = Depends(get_db),
):
    """Create a new board owned by the current user."""
    board = crud.create_board(db, name=payload.name, owner_id=current_user.id)
    return board


@app.post("/api/boards/{board_id}/collaborators")
def add_collaborator(
    board_id: int,
    user_id: str,
    current_user=Depends(auth_module.require_user),
    db: Session = Depends(get_db),
):
    """Add a user as a collaborator on a board (owner only)."""
    board = crud.get_board_entity(db, board_id)
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    if board.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the board owner can add collaborators")
    crud.add_collaborator(db, board_id=board_id, user_id=user_id)
    return {"status": "ok"}


# ── Board & Node REST endpoints ───────────────────────────────────────────────

@app.get("/api/board", response_model=schemas.BoardOut)
def read_board(board_id: int = Query(...), db: Session = Depends(get_db)):
    nodes = crud.get_board(db, board_id=board_id)
    # Touch last_visited_at if the board entity exists
    crud.touch_board(db, board_id)
    return {"nodes": nodes}


def _node_broadcast_payload(event_type: str, node) -> dict:
    return {
        "type": event_type,
        "node": {
            "id": node.id, "type": node.type, "content": node.content,
            "data": node.data, "x": node.x, "y": node.y,
            "createdBy": node.created_by, "parentId": node.parent_id,
        },
    }


@app.post("/api/nodes", response_model=schemas.NodeOut)
async def create_node(
    payload: schemas.NodeCreate,
    board_id: int = Query(...),
    db: Session = Depends(get_db),
):
    node = crud.create_node(
        db, content=payload.content, x=payload.x, y=payload.y,
        created_by=payload.created_by, type=payload.type, data=payload.data,
        parent_id=payload.parent_id, board_id=board_id,
    )
    await _broadcast_to_board(board_id, _node_broadcast_payload("node_created", node))
    return node


@app.patch("/api/nodes/{node_id}", response_model=schemas.NodeOut)
async def update_node(node_id: str, payload: schemas.NodeUpdate, db: Session = Depends(get_db)):
    fields = payload.model_dump(exclude_none=True, exclude={"set_parent_id"})
    node = crud.update_node(db, node_id, set_parent_id=payload.set_parent_id, **fields)
    if not node:
        raise HTTPException(status_code=404, detail="node not found")
    await _broadcast_to_board(node.board_id, _node_broadcast_payload("node_updated", node))
    return node


@app.delete("/api/nodes/{node_id}")
async def delete_node(node_id: str, db: Session = Depends(get_db)):
    node = crud.get_node(db, node_id)
    board_id = node.board_id if node else None
    crud.delete_node(db, node_id)
    if board_id is not None:
        await _broadcast_to_board(board_id, {"type": "node_deleted", "id": node_id})
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
    board_id: int = Form(...),
    db: Session = Depends(get_db),
):
    content = await file.read()
    doc_name = file.filename or "document.txt"
    chunks = _parse_document(content, doc_name)

    if not chunks:
        raise HTTPException(status_code=422, detail="Document is empty or could not be parsed.")

    try:
        embeddings = await ai_gateway.embed_text(chunks)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Embedding failed: {e}")

    crud.store_chunks(db, board_id=board_id, doc_name=doc_name, chunks=chunks, embeddings=embeddings)
    return {"doc_name": doc_name, "chunk_count": len(chunks), "board_id": board_id}


@app.get("/api/documents")
def list_documents(board_id: int = Query(...), db: Session = Depends(get_db)):
    doc_names = crud.list_documents(db, board_id=board_id)
    return {"documents": doc_names, "board_id": board_id}


@app.delete("/api/documents/{doc_name}")
def delete_document(
    doc_name: str,
    board_id: int = Query(...),
    db: Session = Depends(get_db),
):
    n = crud.delete_document(db, board_id=board_id, doc_name=doc_name)
    if n == 0:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"status": "ok", "deleted_chunks": n}


# ── Presence WebSocket — /ws/board/{board_id} ─────────────────────────────────
#
# One room per board.  Each connected client is identified by a session dict:
#   { "ws": WebSocket, "user_id": str, "name": str, "avatar": str, "color": str }
#
# Incoming message types (client → server):
#   { "type": "cursor_move", "x": float, "y": float }
#   { "type": "node_updated", "node": { ...node fields } }
#   { "type": "node_deleted", "id": str }
#
# Outgoing event types (server → client, broadcast to room):
#   { "type": "presence",      "users": [ {userId, name, avatar, color, x?, y?} ] }
#   { "type": "node_updated",  "node": {...} }
#   { "type": "node_deleted",  "id": str }
#   { "type": "node_created",  "node": {...} }  ← injected by AI agent fan-out

# Palette of distinct cursor colours for presence (cycles if >9 users)
_CURSOR_COLORS = [
    "#2f5fe0", "#e05f2f", "#2fc82f", "#c82fc8", "#c8c82f",
    "#2fc8c8", "#c82f5f", "#5fc82f", "#2f5fc8",
]

# board_id → list of session dicts
_rooms: dict[int, list[dict]] = defaultdict(list)


def _presence_payload(room: list[dict]) -> dict:
    return {
        "type": "presence",
        "users": [
            {
                "userId": s["user_id"],
                "name":   s["name"],
                "avatar": s["avatar"],
                "color":  s["color"],
                "x":      s.get("x"),
                "y":      s.get("y"),
            }
            for s in room
        ],
    }


async def _broadcast(room: list[dict], event: dict, exclude_ws: WebSocket | None = None) -> None:
    """Send `event` to every connection in the room, optionally skipping one."""
    dead: list[dict] = []
    payload = json.dumps(event)
    for session in list(room):
        if session["ws"] is exclude_ws:
            continue
        try:
            await session["ws"].send_text(payload)
        except Exception:
            dead.append(session)
    for s in dead:
        if s in room:
            room.remove(s)


async def _broadcast_to_board(board_id: int, event: dict) -> None:
    """Public helper used by the AI agent's chat WS to fan-out node events."""
    room = _rooms.get(board_id)
    if room:
        await _broadcast(room, event)


# Expose for agent to import
app.state.broadcast_to_board = _broadcast_to_board


@app.websocket("/ws/board/{board_id}")
async def board_presence_ws(ws: WebSocket, board_id: int):
    """Presence + real-time node sync WebSocket for a board.

    Auth is read from a `token` query param (easier for WebSocket than headers).
    Unauthenticated connections are accepted as anonymous (read-only presence).
    """
    await ws.accept()

    # Try to identify the user from token query param
    token = ws.query_params.get("token", "")
    user_id = "anon"
    user_name = "Anonymous"
    user_avatar = ""
    if token:
        try:
            payload = auth_module.verify_jwt(token)
            user_id = payload["sub"]
            user_name = payload.get("name") or payload.get("email", "User")
            user_avatar = payload.get("avatar_url") or ""
        except Exception:
            pass  # fall through as anon

    room = _rooms[board_id]
    color_idx = len(room) % len(_CURSOR_COLORS)
    session: dict = {
        "ws":      ws,
        "user_id": user_id,
        "name":    user_name,
        "avatar":  user_avatar,
        "color":   _CURSOR_COLORS[color_idx],
    }
    room.append(session)

    logger.info("presence join  board=%s user=%s", board_id, user_id)

    # Send current presence to everyone (including the new joiner)
    await _broadcast(room, _presence_payload(room))

    db = next(get_db())
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = msg.get("type")

            if msg_type == "cursor_move":
                session["x"] = msg.get("x")
                session["y"] = msg.get("y")
                # Broadcast updated presence (lightweight cursor positions)
                await _broadcast(room, _presence_payload(room), exclude_ws=ws)

            elif msg_type == "node_updated":
                node_data = msg.get("node", {})
                node_id = node_data.get("id") or node_data.get("serverId")
                if node_id:
                    # Persist the change
                    fields = {
                        k: v for k, v in node_data.items()
                        if k in ("content", "data", "x", "y")
                    }
                    if "parent_id" in node_data:
                        crud.update_node(db, node_id, set_parent_id=True,
                                         parent_id=node_data["parent_id"], **fields)
                    else:
                        crud.update_node(db, node_id, **fields)
                    # Fan-out to other clients
                    await _broadcast(room, {"type": "node_updated", "node": node_data}, exclude_ws=ws)

            elif msg_type == "node_deleted":
                node_id = msg.get("id")
                if node_id:
                    crud.delete_node(db, node_id)
                    await _broadcast(room, {"type": "node_deleted", "id": node_id}, exclude_ws=ws)

    except WebSocketDisconnect:
        pass
    finally:
        if session in room:
            room.remove(session)
        if not room:
            _rooms.pop(board_id, None)
        db.close()
        logger.info("presence leave board=%s user=%s", board_id, user_id)
        # Notify remaining clients of updated presence
        if _rooms.get(board_id):
            await _broadcast(_rooms[board_id], _presence_payload(_rooms[board_id]))


# ── WebSocket chat — /ws/chat ─────────────────────────────────────────────────

@app.websocket("/ws/chat")
async def chat_ws(ws: WebSocket, board_id: int = Query(...)):
    """One user message in, a stream of {type: ...} events out:
    node_thinking, node_added, node_updated, node_deleted, token, message_done, error."""
    await ws.accept()
    db = next(get_db())
    history: list[dict] = []

    async def send(event: dict) -> None:
        await ws.send_text(json.dumps(event))

    async def send_and_broadcast(event: dict) -> None:
        """Send to chat subscriber AND fan-out node events to presence room."""
        await send(event)
        if event.get("type") in ("node_added", "node_updated", "node_deleted"):
            # Map agent event types to presence event types
            ptype = {
                "node_added":   "node_created",
                "node_updated": "node_updated",
                "node_deleted": "node_deleted",
            }[event["type"]]
            presence_event = {**event, "type": ptype}
            await _broadcast_to_board(board_id, presence_event)

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
                    send_and_broadcast,
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
            del history[:-12]

            asyncio.create_task(
                ai_gateway.update_board_summary(db, board_id, history)
            )

    except WebSocketDisconnect:
        pass
    finally:
        db.close()