"""
Agent loop: calls Gemini through OpenAI's SDK (Gemini exposes an OpenAI-compatible
endpoint), gives it tools that mutate the board, and streams each action out over
a websocket the moment it happens so the canvas feels alive rather than "submit
and wait".
"""
import os
import json
import uuid
import asyncio
from typing import Callable, Awaitable

from openai import OpenAI
from sqlalchemy.orm import Session

from . import crud

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
MAX_TOOL_TURNS = 6
NODE_SPACING = 260

Send = Callable[[dict], Awaitable[None]]

_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set — add it to backend/.env")
        _client = OpenAI(
            api_key=api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )
    return _client


SYSTEM_PROMPT = """You are a brainstorming partner working alongside a user on an \
infinite whiteboard canvas. You share the board with them — you don't just answer \
questions, you actively add, connect, and tidy up ideas using your tools.

Guidelines:
- Nodes are sticky notes, not paragraphs: a few words to one short sentence each.
- Prefer several small connected nodes over one dense node.
- When an idea relates to one the user already has, pass its id as near_node_id \
  (this places and links your new node near it) or use link_nodes afterwards.
- Don't restate node text back in your reply. After acting, send one short, \
  conversational sentence about what you did or what you're noticing.
- If the user is just chatting and there's nothing board-worthy yet, it's fine to \
  reply with no tool calls at all.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "add_node",
            "description": "Add a new idea node to the whiteboard.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Short node text."},
                    "near_node_id": {
                        "type": "string",
                        "description": "Optional existing node id to place this next to and link from.",
                    },
                },
                "required": ["content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_node",
            "description": "Change the text of an existing node.",
            "parameters": {
                "type": "object",
                "properties": {
                    "node_id": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["node_id", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "link_nodes",
            "description": "Draw a connection between two existing nodes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source_id": {"type": "string"},
                    "target_id": {"type": "string"},
                },
                "required": ["source_id", "target_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_node",
            "description": "Remove a node that's redundant or resolved.",
            "parameters": {
                "type": "object",
                "properties": {"node_id": {"type": "string"}},
                "required": ["node_id"],
            },
        },
    },
]


def _board_snapshot(db: Session) -> str:
    nodes, edges = crud.get_board(db)
    if not nodes:
        return "The board is currently empty."
    node_lines = "\n".join(f'- {n.id} ({n.created_by}): "{n.content}"' for n in nodes)
    edge_lines = "\n".join(f"- {e.source_id} -> {e.target_id}" for e in edges) or "(none)"
    return f"Current nodes:\n{node_lines}\n\nCurrent links:\n{edge_lines}"


def _next_position(db: Session, near_node_id: str | None) -> dict:
    nodes, _ = crud.get_board(db)
    by_id = {n.id: n for n in nodes}

    if near_node_id and near_node_id in by_id:
        origin = by_id[near_node_id]
        bx, by = origin.x, origin.y
    elif nodes:
        bx = sum(n.x for n in nodes) / len(nodes)
        by = max(n.y for n in nodes)
    else:
        bx, by = 80, 80

    occupied = {(round(n.x / 40), round(n.y / 40)) for n in nodes}
    x, y = bx + NODE_SPACING, by
    hops = 0
    while (round(x / 40), round(y / 40)) in occupied and hops < 15:
        y += 150
        hops += 1
    return {"x": x, "y": y}


async def _execute_tool(db: Session, name: str, args: dict, send: Send) -> dict:
    if name == "add_node":
        temp_id = f"tmp-{uuid.uuid4().hex[:8]}"
        pos = _next_position(db, args.get("near_node_id"))
        await send({"type": "node_thinking", "tempId": temp_id, **pos})
        await asyncio.sleep(0.5)  # let the dashed "thinking" state actually be seen

        node = crud.create_node(db, content=args["content"], x=pos["x"], y=pos["y"], created_by="agent")
        await send({"type": "node_added", "tempId": temp_id, "node": _node_dict(node)})

        near_id = args.get("near_node_id")
        if near_id and crud.get_node(db, near_id):
            edge = crud.create_edge(db, source_id=near_id, target_id=node.id)
            await send({"type": "edge_added", "edge": _edge_dict(edge)})
        return {"status": "ok", "node_id": node.id}

    if name == "edit_node":
        node = crud.update_node(db, args["node_id"], content=args.get("content"))
        if not node:
            return {"status": "error", "message": "node not found"}
        await send({"type": "node_updated", "node": _node_dict(node)})
        return {"status": "ok"}

    if name == "delete_node":
        ok = crud.delete_node(db, args["node_id"])
        if ok:
            await send({"type": "node_deleted", "id": args["node_id"]})
        return {"status": "ok" if ok else "error", "message": None if ok else "node not found"}

    if name == "link_nodes":
        if not (crud.get_node(db, args["source_id"]) and crud.get_node(db, args["target_id"])):
            return {"status": "error", "message": "source or target not found"}
        edge = crud.create_edge(db, args["source_id"], args["target_id"])
        await send({"type": "edge_added", "edge": _edge_dict(edge)})
        return {"status": "ok", "edge_id": edge.id}

    return {"status": "error", "message": f"unknown tool '{name}'"}


async def _stream_text(text: str, send: Send) -> None:
    """Fake per-word streaming for the wrap-up message — cheap, reliable, and reads
    live in the chat panel without needing token-level streaming through a tool loop."""
    words = text.split(" ")
    for i in range(0, len(words), 3):
        await send({"type": "token", "content": " ".join(words[i:i + 3]) + " "})
        await asyncio.sleep(0.03)
    await send({"type": "message_done"})


def _node_dict(n) -> dict:
    return {"id": n.id, "content": n.content, "x": n.x, "y": n.y, "created_by": n.created_by}


def _edge_dict(e) -> dict:
    return {"id": e.id, "source_id": e.source_id, "target_id": e.target_id}


async def run_agent_turn(db: Session, user_message: str, history: list, send: Send) -> str | None:
    """Runs one agentic turn: the model can call tools any number of times (each
    executed and broadcast immediately) before giving a final text reply."""
    client = get_client()
    messages = [
        {"role": "system", "content": f"{SYSTEM_PROMPT}\n\n{_board_snapshot(db)}"},
        *history,
        {"role": "user", "content": user_message},
    ]

    for _ in range(MAX_TOOL_TURNS):
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=MODEL,
            messages=messages,
            tools=TOOLS,
        )
        message = response.choices[0].message
        tool_calls = message.tool_calls or []

        if not tool_calls:
            text = message.content or "Done."
            await _stream_text(text, send)
            return text

        messages.append(message.model_dump(exclude_none=True))
        for call in tool_calls:
            args = json.loads(call.function.arguments or "{}")
            result = await _execute_tool(db, call.function.name, args, send)
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(result),
            })

    fallback = "That's a lot at once — I'll pause here so you can take a look."
    await _stream_text(fallback, send)
    return fallback
