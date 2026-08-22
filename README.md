# Skretch
A full-stack collaborative canvas for brainstorming. Scratch your ideas on na infinite whiteboard, synced live across everyone looking at it, with an AI copilot that can read the board and export it as a structured document.

![Vue](https://img.shields.io/badge/Vue-3-42b883)
![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688)
![Gemini](https://img.shields.io/badge/Gemini-AI%20%2B%20embeddings-8e44ad)
![WebSockets](https://img.shields.io/badge/Realtime-WebSockets-blue)
![License](https://img.shields.io/badge/License-MIT-green)

## Features
### Boards
- **Board creation with templates** — get started quick with templates eg. "Kanban","Retrospective", "OKR" or a fresh,  whiteboard
- **Delete a board** — remove obsolete boards, otherwise they'll persist in the database with their respective nodes
- **Search board by name** — live search without reloading the page or sending a get request

### Canvas
- **Infinite board** — pan, zoom and drop sticky notes, images, and frames anywhere
- **Sticky notes** - customise with color, reactions
- **Frames** — colorable, draggable containers that auto-adopt any node dropped inside their bounds as children, and orphaning free nodes outside
- **Live multiplayer cursors** — see collaborators' names and cursors move on the board in real time
- **Presence-aware editing** — every board tracks who's currently on it
- **Undo/redo** — full checkpoint history, keyboard-driven (`⌘Z`)


### AI Copilot
- **In-canvas chat** — helps you populate the board with ideas, organize, classify by theme, research (with citations!) whilst taking in your existing canvas as context
- **Document import as context** — have a project description doc you must follow? share your specs as grounding material for canvas planning assistance (brief) as well as the exported document (verbose)
- **Gemini-powered** — uses Gemini's free tier for both the chat/agent LLM and content chunking, embeddings, retrieval, generation

### Export
- **Export to Google Docs** — the AI reads your board (frames, stickies, notes) and writes a structured document with real headings and sections
- **Format-aware** — choose Auto, Essay, or PRD output shape before exporting
- **Structured JSON preview** — inspect exactly what will be sent to the AI before you export

### Backend & Authentication
- **Google OAuth** — sign in with Google; the same token set also authorizes on-behalf-of Drive/Docs export
- **Guest mode** — one-click demo entry with no signup, dropped straight onto a shared live board so first-time visitors can see multiplayer working immediately
- **JWT sessions** — stateless bearer-token auth on every REST and WebSocket call
- **Owner-scoped data** — boards, nodes, and uploaded documents are scoped to their creator

### Architecture
- **Frame-membership as geometric containment** — a node's parent frame is derived from its center point at drag-stop, not stored as an explicit "drop target," so reparenting stays correct even after independent moves of both the node and its frame
- **Local-first mutation, deferred persistence** — high-frequency gestures (drag, resize) mutate store state directly and only hit the network once, on gesture-end, instead of on every tick. The moved sticky note will only appear at its destination on collaborators' screens but appear 'dragged' by the user.
- **WS + REST dual-write reconciliation** — the store dedupes self-originated WebSocket echoes against in-flight REST responses using server ID, so a node created locally never gets double-inserted when its own broadcast comes back

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Vue 3 + Vite |
| Canvas engine | Vue Flow (`@vue-flow/core`, `@vue-flow/background`, `@vue-flow/controls`) |
| State | Pinia (`board`, `tool`, `auth` stores) |
| Realtime | WebSockets (per-board presence + live node sync) |
| Backend | FastAPI |
| Database | SQLAlchemy ORM (Postgres-compatible) |
| Authentication | Google OAuth 2.0 + JWT (session tokens) |
| AI / Embeddings | Google Gemini API (free tier) |
| Export | Google Docs API |
| Styling | Scoped CSS + CSS Custom Properties |

## Getting Started

### Prerequisites
- Node.js 20+
- Python 3.11+
- A Google Cloud project with OAuth credentials and the Docs/Drive APIs enabled
- A free-tier Gemini API key
- A Postgres database (Neon remote)

### Environment Variables

Create a `server/.env` file with:

```env
DATABASE_URL=your_postgres_connection_string
GOOGLE_CLIENT_ID=your_google_oauth_client_id
GOOGLE_CLIENT_SECRET=your_google_oauth_client_secret
GOOGLE_REDIRECT_URI=http://localhost:8000/api/auth/google/callback
JWT_SECRET=your_jwt_secret_key
GEMINI_API_KEY=your_gemini_api_key
FRONTEND_URL=http://localhost:5173
```

Create a frontend `.env` file with:

```env
VITE_API_URL=http://localhost:8000
```

### Install & Run

```bash
# Install backend dependencies
cd server && pip install -r requirements.txt

# Start backend server (http://localhost:8000)
uvicorn main:app --reload

# Install frontend dependencies
cd frontend && npm install

# Start frontend dev server (http://localhost:5173)
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

## Project Structure

```
backend/           Fastapi backend
  app/
    agent.py
    ai_gateway.py  queue req to gemini, work around freetier
    auth.py
    crud.py
    database.py
    export.py
    main.py        App entry point, routers
    models.py      SQLAlchemy models
    schemas.py     Pydantic request/response 
    templates.py
  .gitignore
  requirements.txt
frontend/
  src/
    api/
      client.js
    components/
      ChatPopover.vue
      ExportNavbar.vue
      Frame.vue
      StickyNoteNode.vue
      Toolbar.vue
    composables/
      useAgentChat.js
      useBoardPresence.js
    pages/
      BoardsMenuPage.vue
      Canvas.vue
      LoginPage.vue
    router/
      index.js
    stores/
      auth.js
      board.js
      tool.js
    utils/
      image.js     not done
      layout.js
      nodeTypes.js
    App.vue
    main.js
    style.css
  index.html
  vite.config.js
```

## API Endpoints

### Authentication
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/auth/google` | Redirect to Google's OAuth consent screen |
| GET | `/api/auth/google/callback` | Google OAuth callback, issues a JWT |
| POST | `/api/auth/guest` | Create/reuse a demo guest identity, returns a JWT |
| GET | `/api/auth/me` | Return the current authenticated user |

### Boards
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/boards` | List boards owned by or shared with the user |
| POST | `/api/boards` | Create a new board |
| GET | `/api/board?board_id=<id>` | Get a board and all its nodes |
| DELETE | `/api/boards/<id>` | Delete a board and its nodes |

### Nodes
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/nodes?board_id=<id>` | Create a node |
| PATCH | `/api/nodes/<id>` | Update a node's content, data, position, or parent |
| DELETE | `/api/nodes/<id>` | Delete a node (children are orphaned, not cascaded) |

### Documents
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/documents` | Upload a document for RAG context (multipart) |
| GET | `/api/documents?board_id=<id>` | List uploaded documents for a board |
| DELETE | `/api/documents/<name>?board_id=<id>` | Delete an uploaded document |

### Realtime
| Protocol | Endpoint | Description |
|---|---|---|
| WS | `/ws/board/<board_id>` | Presence + live node create/update/delete broadcast |

## Data Model

### Node
```python
{
  id: str,               # Server-generated unique ID
  type: str,              # "sticky" | "image" | "frame" | "document"
  content: str,
  data: dict,              # Type-specific fields (color, width/height, image URL, embedding…)
  x: float,
  y: float,
  created_by: str,
  parent_id: Optional[str] # Frame this node belongs to, if any
}
```

### Board
```python
{
  board_id: int,
  name: str,
  owner_id: Optional[str],
  last_visited_at: Optional[datetime],
  created_at: Optional[datetime],
}
```

### User
```python
{
  id: str,
  google_id: str,                    # Unique — includes guest placeholder IDs
  email: str,
  name: str,
  avatar_url: Optional[str],
  google_access_token: Optional[str],   # For Drive/Docs export on the user's behalf
  google_refresh_token: Optional[str],
  google_token_expiry: Optional[float],
}
```

## Key Architectural Decisions

### Frame Membership via Geometric Containment
A node's `parent_id` isn't set by an explicit "drop zone" event — it's derived by checking whether the node's center point falls inside a frame's rectangle at drag-stop. This means a frame that gets resized or moved automatically picks up or releases members without any special-cased event wiring; the same `reconcileNodeParent`/`reconcileFrameMembers` check handles both directions.

### Local-First Mutation for High-Frequency Gestures
Early versions called the persistence API (`api.updateNode`) on every `pointermove` during a drag or resize — meaning a single resize gesture could fire dozens of HTTP requests per second, one per animation frame. The store now exposes two tiers of write:
- `setNodeDataLocal()` — synchronous, in-memory only, safe to call every tick
- `commitNodeData()` — mutates locally **and** persists, meant to be called once per gesture

Resize and drag now both follow the same pattern: local-only updates while the gesture is in progress, one persisted write on release.

### Memoized Node Projection for Vue Flow
`board.nodes` is a single reactive array; any computed that maps over it re-runs in full whenever *any* node changes, which by default allocates a brand-new object for every node on every recompute — handing Vue Flow a fresh object identity for the entire board on every single move, forcing it to re-diff nodes that never changed. The `flowNodes` computed that feeds Vue Flow now keeps a per-node object cache keyed by node ID: a node only gets a new object if a field Vue Flow actually renders from (position, type, z-index, draggable/connectable, or the underlying data reference) has changed. Every other node keeps the exact same object reference across recomputes, so Vue Flow's internal diffing sees "unchanged" for the vast majority of the board on every drag or resize tick — this is what fixed drag/resize lag that was reproducible even with a single user on the board.

## License

MIT