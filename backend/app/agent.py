"""
Agent loop: calls Gemini through OpenAI's SDK (Gemini exposes an OpenAI-compatible
endpoint), gives it tools that mutate the board, and streams each action out over
a websocket the moment it happens so the canvas feels alive rather than "submit
and wait".
"""
import json
import uuid
import asyncio
from typing import Callable, Awaitable

from sqlalchemy.orm import Session

from . import crud, ai_gateway

MAX_TOOL_TURNS = 6
NODE_SPACING = 260
FRAME_PADDING = 40

Send = Callable[[dict], Awaitable[None]]


SYSTEM_PROMPT = """You are a brainstorming partner working alongside a user on an \
infinite whiteboard canvas. You share the board with them — you don't just answer \
questions, you actively add and organize ideas using your tools.

Guidelines:
- Nodes are sticky notes, not paragraphs: a few words to one short sentence each.
- Prefer several small nodes over one dense node.
- Frames are the only way to group ideas. If you're adding related nodes, either \
  drop them into an existing frame (parent_id) or create a new frame with \
  create_frame and put them inside it. An ungrouped pile of notes is a smell — \
  group things once a cluster of 3+ related nodes exists.
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
                    "parent_id": {
                        "type": "string",
                        "description": "Optional frame id to place this node inside.",
                    },
                    "near_node_id": {
                        "type": "string",
                        "description": "Optional existing node id to place this near "
                                       "(ignored if parent_id is set).",
                    },
                    "node_type": {
                        "type": "string",
                        "enum": ["sticky", "image","frame"],
                        "description": "Defaults to 'sticky', a short sticky note containing an insightful idea, a few words to 2 sentences long. Use 'frame' to create a container housing other nodes of similar theme. Use 'image' for images found online that illustrate well your point." ,
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
            "name": "delete_node",
            "description": "Remove a node that's redundant or resolved.",
            "parameters": {
                "type": "object",
                "properties": {"node_id": {"type": "string"}},
                "required": ["node_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_frame",
            "description": "Create a labeled frame that groups a set of existing nodes together.",
            "parameters": {
                "type": "object",
                "properties": {
                    "label": {"type": "string", "description": "Short name for this cluster of ideas."},
                    "node_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Existing node ids to move inside the new frame.",
                    },
                },
                "required": ["label"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "move_node",
            "description": "Move a node into a frame, or out to the top level.",
            "parameters": {
                "type": "object",
                "properties": {
                    "node_id": {"type": "string"},
                    "parent_id": {
                        "type": ["string", "null"],
                        "description": "Target frame id, or null to remove from any frame.",
                    },
                },
                "required": ["node_id", "parent_id"],
            },
        },
    },
]


def _board_snapshot(db: Session) -> str:
    nodes = crud.get_board(db)
    nodes = [n for n in nodes if n.type != "stroke"]
    if not nodes:
        return "The board is currently empty."

    frames = {n.id: n for n in nodes if n.type == "frame"}
    by_parent: dict[str | None, list] = {}
    for n in nodes:
        if n.type == "frame":
            continue
        by_parent.setdefault(n.parent_id, []).append(n)

    lines = []
    for fid, frame in frames.items():
        lines.append(f'Frame {fid} "{frame.content}":')
        for n in by_parent.get(fid, []):
            lines.append(f'  - {n.id} ({n.created_by}, {n.type}): "{n.content}"')
    ungrouped = by_parent.get(None, [])
    if ungrouped:
        lines.append("Ungrouped:")
        for n in ungrouped:
            lines.append(f'  - {n.id} ({n.created_by}, {n.type}): "{n.content}"')
    return "\n".join(lines)


def _next_position(db: Session, parent_id: str | None, near_node_id: str | None) -> dict:
    nodes = crud.get_board(db)

    if parent_id:
        frame = crud.get_node(db, parent_id)
        siblings = [n for n in nodes if n.parent_id == parent_id]
        if frame:
            bx = frame.x + FRAME_PADDING
            by = frame.y + FRAME_PADDING + len(siblings) * 90
            return {"x": bx, "y": by}

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
        parent_id = args.get("parent_id")
        if parent_id and not crud.get_node(db, parent_id):
            parent_id = None
        temp_id = f"tmp-{uuid.uuid4().hex[:8]}"
        pos = _next_position(db, parent_id, args.get("near_node_id"))
        await send({"type": "node_thinking", "tempId": temp_id, **pos})
        await asyncio.sleep(0.5)  # let the dashed "thinking" state actually be seen

        node = crud.create_node(
            db, content=args["content"], x=pos["x"], y=pos["y"],
            created_by="agent", type=args.get("node_type", "sticky"), parent_id=parent_id,
        )
        await send({"type": "node_added", "tempId": temp_id, "node": _node_dict(node)})
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

    if name == "create_frame":
        node_ids = args.get("node_ids") or []
        members = [crud.get_node(db, nid) for nid in node_ids]
        members = [m for m in members if m]

        if members:
            fx = min(m.x for m in members) - FRAME_PADDING
            fy = min(m.y for m in members) - FRAME_PADDING
        else:
            fx, fy = _next_position(db, None, None).values()

        frame = crud.create_node(
            db, content=args["label"], x=fx, y=fy,
            created_by="agent", type="frame", parent_id=None,
        )
        await send({"type": "node_added", "tempId": None, "node": _node_dict(frame)})

        for m in members:
            updated = crud.update_node(db, m.id, parent_id=frame.id)
            await send({"type": "node_updated", "node": _node_dict(updated)})

        return {"status": "ok", "frame_id": frame.id}

    if name == "move_node":
        parent_id = args.get("parent_id")
        if parent_id and not crud.get_node(db, parent_id):
            return {"status": "error", "message": "parent frame not found"}
        node = crud.update_node(db, args["node_id"], parent_id=parent_id, set_parent_id=True)
        if not node:
            return {"status": "error", "message": "node not found"}
        await send({"type": "node_updated", "node": _node_dict(node)})
        return {"status": "ok"}

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
    return {
        "id": n.id, "type": n.type, "content": n.content, "data": n.data,
        "x": n.x, "y": n.y, "created_by": n.created_by, "parent_id": n.parent_id,
    }


async def run_agent_turn(db: Session, user_message: str, history: list, send: Send) -> str | None:
    """Runs one agentic turn: the model can call tools any number of times (each
    executed and broadcast immediately) before giving a final text reply."""
    messages = [
        {"role": "system", "content": f"{SYSTEM_PROMPT}\n\n{_board_snapshot(db)}"},
        *history,
        {"role": "user", "content": user_message},
    ]

    for _ in range(MAX_TOOL_TURNS):
        response = await ai_gateway.generate_governed(model=ai_gateway.MODEL, messages=messages, tools=TOOLS)
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