"""
Agent loop: calls Gemini through OpenAI's SDK (Gemini exposes an OpenAI-compatible
endpoint), gives it tools that mutate the board, and streams each action out over
a websocket the moment it happens so the canvas feels alive rather than "submit
and wait".
"""
import json
import math
import uuid
import asyncio
from typing import Callable, Awaitable

from sqlalchemy.orm import Session

from . import crud, ai_gateway

MAX_TOOL_TURNS = 12

# ── layout constants ──────────────────────────────────────────────────────────
STICKY_W = 240       # px width assumed for a sticky note
STICKY_H = 160       # px height assumed for a sticky note (2-line note)
FRAME_LABEL_H = 48   # vertical space reserved for the frame's title bar
FRAME_PAD = 40       # inner padding around the grid of children
FRAME_COL_W = 260    # column width inside a frame (sticky + inter-gap)
FRAME_ROW_H = 300    # row height inside a frame
FRAME_COLS = 2       # default columns for notes inside a frame
FRAME_H_GAP = 60     # horizontal gap between top-level frames
FRAME_V_GAP = 80     # vertical gap between rows of top-level frames

Send = Callable[[dict], Awaitable[None]]


SYSTEM_PROMPT = """You are a canvas brainstorming partner. You work alongside the \
user on an infinite whiteboard. You don't just answer — you *actively populate \
and organise* the board using your tools so the user can see structured thinking \
take shape in real-time.

## Canvas philosophy
- **Frames are sections**: treat each frame like a document section or slide. \
  Its label should be a crisp, meaningful title (3–6 words) that could become a \
  heading in a Google Doc or slide title.
- **Stickies are insights, not labels**: each sticky should contain 1–2 complete \
  sentences articulating an insight, an action, a question, or a data point — \
  not just a keyword. Think in full thoughts.
- **Cluster by theme**: always group 3 or more related stickies inside a frame. \
  Ungrouped piles of notes are a signal something needs organizing.
- **Sequence matters**: when content is sequential (steps, timeline, priorities), \
  lay frames left-to-right so the board reads like a story.
- **Research before concluding**: when the user asks about trends, competition, \
  market, or anything requiring current data, call `research_topic` first to \
  ground your response in real information.
- **Check documents**: when the user references their project, specs, \
  requirements, or any detail that might be in uploaded documents, call \
  `retrieve_context` first.

## Tool discipline
- Use `create_frame` to make a new labeled container, then `add_node` with \
  `parent_id` to fill it.
- Never use `add_node` with `node_type: "frame"` — always use `create_frame`.
- **Before calling `create_frame`, check the board state above.** If a frame \
  with a similar topic/label already exists, add new stickies into that existing \
  frame using `add_node` with the existing frame's `parent_id`. Only call \
  `create_frame` when the topic is genuinely new and has no existing frame.
- For research: `research_topic` → returns summary + citations → you then create \
  a frame (or reuse an existing one on the same topic) with stickies for each key \
  finding, each carrying `citations` in data.
- For document context: `retrieve_context` → returns relevant passages → you \
  distil them into stickies with `data.source` attribution.

## Reply style
After acting, write one concise paragraph (2–5 sentences) that synthesises what \
you found, why it matters, and what the user should think about next. Do not just \
list what you placed on the board — add genuine commentary, a contrarian angle, \
or a follow-up question that deepens the thinking. If no board action was taken, \
give a thoughtful response in chat only.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "add_node",
            "description": (
                "Add a new sticky note to the board. "
                "To create a frame/container, use create_frame instead. "
                "To add a note inside a frame, set parent_id."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "1–2 complete sentences articulating the insight, action item, question, or data point.",
                    },
                    "parent_id": {
                        "type": "string",
                        "description": "Frame id to place this sticky inside. Required when adding notes to a theme group.",
                    },
                    "near_node_id": {
                        "type": "string",
                        "description": "Optional: place this note near an existing node (ignored if parent_id is set).",
                    },
                    "node_type": {
                        "type": "string",
                        "enum": ["sticky"],
                        "description": "Always 'sticky'. Use create_frame to create containers.",
                    },
                    "citations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "url": {"type": "string"},
                            },
                        },
                        "description": "Optional: web citations from research. Each item has {title, url}.",
                    },
                    "source": {
                        "type": "object",
                        "description": "Optional: document source when content comes from retrieve_context. {doc_name, chunk_index}",
                        "properties": {
                            "doc_name": {"type": "string"},
                            "chunk_index": {"type": "integer"},
                        },
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
            "description": "Update the text of an existing node.",
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
            "description": "Remove a node that is redundant, incorrect, or resolved.",
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
            "description": (
                "Create a labeled frame container, optionally capturing existing nodes into it. "
                "Labels written as: 'Header, clarifying subheader'. "
                "IMPORTANT: First check the board state in the system prompt. If a frame on the same "
                "topic already exists, do NOT call this — use add_node with that frame's id as parent_id instead. "
                "Only create a new frame when the topic is genuinely absent from the board."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "label": {
                        "type": "string",
                        "description": "Concise section title (3–6 words). Will become a slide title or doc heading.",
                    },
                    "node_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Existing node ids to move inside this frame (optional).",
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
            "description": "Move a node into a frame, or release it to the top level.",
            "parameters": {
                "type": "object",
                "properties": {
                    "node_id": {"type": "string"},
                    "parent_id": {
                        "type": ["string", "null"],
                        "description": "Target frame id, or null to move to top level.",
                    },
                },
                "required": ["node_id", "parent_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "research_topic",
            "description": (
                "Search the web for current information about a topic using Google Search grounding. "
                "Use this when the user asks about trends, competition, market data, news, or any "
                "topic that benefits from up-to-date information. Returns a research summary and "
                "a list of citations (web sources) you should attach to the nodes you create."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query — be specific and targeted.",
                    },
                    "context": {
                        "type": "string",
                        "description": "Brief description of why this research is needed, to help focus the summary.",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "retrieve_context",
            "description": (
                "Search the project documents uploaded by the user for relevant context. "
                "Use this when the user references their project, specs, requirements, briefs, "
                "or any detail that might be in uploaded documents. Returns relevant text passages."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "What to search for in the project documents.",
                    },
                },
                "required": ["query"],
            },
        },
    },
]


# ── layout engine ─────────────────────────────────────────────────────────────

def _frame_size(child_count: int) -> tuple[float, float]:
    """Return (width, height) for a frame hosting `child_count` sticky notes."""
    cols = FRAME_COLS
    rows = max(1, math.ceil(child_count / cols))
    w = cols * FRAME_COL_W + 2 * FRAME_PAD
    h = rows * FRAME_ROW_H + 2 * FRAME_PAD + FRAME_LABEL_H
    return w, h


def _next_top_level_frame_pos(db: Session, board_id: int) -> tuple[float, float]:
    """Return (x, y) for a new top-level frame, placed to the right of all
    existing frames (or at origin if none)."""
    nodes = crud.get_board(db, board_id)
    frames = [n for n in nodes if n.type == "frame"]
    if not frames:
        return 80.0, 80.0
    # place to the right of the rightmost frame; assume frame widths from data
    rightmost_x = 0.0
    for f in frames:
        fw = (f.data or {}).get("width", _frame_size(0)[0])
        rightmost_x = max(rightmost_x, f.x + fw)
    return rightmost_x + FRAME_H_GAP, 80.0


def _next_child_pos(db: Session, parent_id: str, board_id: int) -> tuple[float, float]:
    """Return (x, y) for a new child node inside `parent_id`, using a 2-col grid."""
    frame = crud.get_node(db, parent_id)
    if not frame:
        return 0.0, 0.0
    siblings = [n for n in crud.get_board(db, board_id) if n.parent_id == parent_id]
    idx = len(siblings)
    col = idx % FRAME_COLS
    row = idx // FRAME_COLS
    x = frame.x + FRAME_PAD + col * FRAME_COL_W
    y = frame.y + FRAME_LABEL_H + FRAME_PAD + row * FRAME_ROW_H
    return x, y


def _next_position(db: Session, parent_id: str | None, near_node_id: str | None, board_id: int) -> dict:
    if parent_id:
        x, y = _next_child_pos(db, parent_id, board_id)
        return {"x": x, "y": y}

    nodes = [n for n in crud.get_board(db, board_id) if n.type != "stroke"]
    by_id = {n.id: n for n in nodes}

    if near_node_id and near_node_id in by_id:
        origin = by_id[near_node_id]
        return {"x": origin.x + STICKY_W + 20, "y": origin.y}

    if not nodes:
        return {"x": 80.0, "y": 80.0}

    # Place below the lowest node with some offset
    bx = sum(n.x for n in nodes) / len(nodes)
    by = max(n.y for n in nodes) + STICKY_H + 30
    return {"x": bx, "y": by}


def _reaction_tag(n) -> str:
    reactions = (n.data or {}).get("reactions", {})
    active = {k: v for k, v in reactions.items() if v}
    if not active:
        return ""
    return f" [reactions: {', '.join(f'{k}×{v}' for k, v in active.items())}]"


def _node_line(n) -> str:
    cites = len((n.data or {}).get("citations", []))
    cite_tag = f" [{cites} citation(s)]" if cites else ""
    src = (n.data or {}).get("source", {})
    src_tag = f" [from {src.get('doc_name', '')}]" if src else ""
    reaction_tag = _reaction_tag(n)
    return f'  - {n.id} ({n.type}, {n.created_by}) at ({n.x:.0f},{n.y:.0f}): "{n.content}"{cite_tag}{src_tag}{reaction_tag}'


def _board_snapshot(db: Session, board_id: int) -> str:
    """Textual snapshot of the board for injection into the system prompt."""
    nodes = crud.get_board(db, board_id)
    nodes = [n for n in nodes if n.type != "stroke"]
    if not nodes:
        return "The board is currently empty."

    frames = {n.id: n for n in nodes if n.type == "frame"}
    by_parent: dict[str | None, list] = {}
    for n in nodes:
        if n.type == "frame":
            continue
        by_parent.setdefault(n.parent_id, []).append(n)

    lines = ["## Current board state\n"]
    for fid, frame in frames.items():
        lines.append(f'Frame {fid!r} — "{frame.content}" at ({frame.x:.0f}, {frame.y:.0f}):')
        for n in by_parent.get(fid, []):
            lines.append(_node_line(n))

    ungrouped = by_parent.get(None, [])
    if ungrouped:
        lines.append("Ungrouped nodes:")
        for n in ungrouped:
            lines.append(_node_line(n))

    return "\n".join(lines)


# ── tool execution ────────────────────────────────────────────────────────────

async def _execute_tool(
    db: Session,
    name: str,
    args: dict,
    send: Send,
    board_id: int,
    attached_doc_names: list[str] | None = None,
) -> dict:

    if name == "add_node":
        parent_id = args.get("parent_id")
        if parent_id and not crud.get_node(db, parent_id):
            parent_id = None
        temp_id = f"tmp-{uuid.uuid4().hex[:8]}"
        pos = _next_position(db, parent_id, args.get("near_node_id"), board_id)
        node_type = args.get("node_type", "sticky")
        # Build data payload — carry citations and source if provided
        data: dict = {}
        if args.get("citations"):
            data["citations"] = args["citations"]
        if args.get("source"):
            data["source"] = args["source"]

        await send({"type": "node_thinking", "tempId": temp_id, "nodeType": node_type, **pos})
        await asyncio.sleep(0.4)

        node = crud.create_node(
            db, content=args["content"], x=pos["x"], y=pos["y"],
            created_by="agent", type=node_type, parent_id=parent_id,
            data=data, board_id=board_id,
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

        # Determine frame position
        if members:
            fx = min(m.x for m in members) - FRAME_PAD
            fy = min(m.y for m in members) - FRAME_LABEL_H - FRAME_PAD
        else:
            fx, fy = _next_top_level_frame_pos(db, board_id)

        # Compute frame dimensions based on how many children will be inside
        fw, fh = _frame_size(max(len(members), 1))

        frame_data = {"width": fw, "height": fh}
        frame = crud.create_node(
            db, content=args["label"], x=fx, y=fy,
            created_by="agent", type="frame", parent_id=None,
            data=frame_data, board_id=board_id,
        )
        await send({"type": "node_added", "tempId": None, "node": _node_dict(frame)})

        # Move existing members into the frame and reposition them on the grid
        for idx, m in enumerate(members):
            col = idx % FRAME_COLS
            row = idx // FRAME_COLS
            nx = fx + FRAME_PAD + col * FRAME_COL_W
            ny = fy + FRAME_LABEL_H + FRAME_PAD + row * FRAME_ROW_H
            updated = crud.update_node(db, m.id, parent_id=frame.id, x=nx, y=ny, set_parent_id=True)
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

    if name == "research_topic":
        query = args.get("query", "")
        context = args.get("context", "")
        try:
            summary, citations = await ai_gateway.generate_with_search(
                query=query, context=context
            )
        except Exception as e:
            return {"status": "error", "message": f"Research failed: {e}"}
        return {
            "status": "ok",
            "summary": summary,
            "citations": citations,
            "instruction": (
                "Use the summary above to create a frame with 3-5 stickies, each capturing a key "
                "finding. Attach relevant citations to each sticky via the 'citations' field in add_node."
            ),
        }

    if name == "retrieve_context":
        query = args.get("query", "")
        try:
            chunks = await ai_gateway.retrieve_rag_context(
                db=db, board_id=board_id, query=query,
                doc_names=attached_doc_names
            )
        except Exception as e:
            return {"status": "error", "message": f"Retrieval failed: {e}"}
        if not chunks:
            return {"status": "ok", "passages": [], "message": "No relevant passages found in uploaded documents."}
        passages = [
            {"text": c.text, "doc_name": c.doc_name, "chunk_index": c.chunk_index}
            for c in chunks
        ]
        return {
            "status": "ok",
            "passages": passages,
            "instruction": (
                "Use these passages to distil key insights as sticky notes. "
                "Set data.source = {doc_name, chunk_index} on each node you create from this context."
            ),
        }

    return {"status": "error", "message": f"unknown tool '{name}'"}


# ── streaming helper ──────────────────────────────────────────────────────────

async def _stream_text(text: str, send: Send) -> None:
    """Word-group streaming for the wrap-up message."""
    words = text.split(" ")
    for i in range(0, len(words), 3):
        await send({"type": "token", "content": " ".join(words[i:i + 3]) + " "})
        await asyncio.sleep(0.03)
    await send({"type": "message_done"})


def _node_dict(n) -> dict:
    return {
        "id": n.id, "type": n.type, "content": n.content, "data": n.data or {},
        "x": n.x, "y": n.y, "createdBy": n.created_by, "parentId": n.parent_id,
    }


# ── main agent turn ───────────────────────────────────────────────────────────

async def run_agent_turn(
    db: Session,
    user_message: str,
    history: list,
    send: Send,
    board_id: int,
    attached_doc_names: list[str] | None = None,
    board_summary: str | None = None,
) -> str | None:
    """Runs one agentic turn: the model can call tools any number of times (each
    executed and broadcast immediately) before giving a final text reply."""

    # Build system prompt with board snapshot + board memory
    board_state = _board_snapshot(db, board_id)
    sys_content = SYSTEM_PROMPT + "\n\n" + board_state
    if board_summary:
        sys_content += f"\n\n## Project memory\n{board_summary}"
    if attached_doc_names:
        sys_content += (
            f"\n\n## Uploaded project documents (available via retrieve_context)\n"
            + "\n".join(f"- {d}" for d in attached_doc_names)
        )

    messages = [
        {"role": "system", "content": sys_content},
        *history,
        {"role": "user", "content": user_message},
    ]

    for _ in range(MAX_TOOL_TURNS):
        response = await ai_gateway.generate_governed(
            model=ai_gateway.MODEL, messages=messages, tools=TOOLS
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
            result = await _execute_tool(
                db, call.function.name, args, send,
                board_id=board_id,
                attached_doc_names=attached_doc_names,
            )
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(result),
            })

    fallback = "That's a lot to process — I've paused so you can review what's on the board. Let me know how to continue."
    await _stream_text(fallback, send)
    return fallback
