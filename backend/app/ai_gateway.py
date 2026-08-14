"""
Governed Gemini gateway — the single choke point every Gemini call goes
through.
  1. SERIALIZE — every OpenAI-compat call shares one asyncio.Lock.
  2. SPACE — consecutive calls are spaced by GEMINI_MIN_SPACING_S.
  3. RETRY — 429s are retried with backoff; daily quota errors fail fast.

Additional capabilities beyond the OpenAI-compat path:
  - generate_with_search()  — Gemini native SDK + Google Search grounding
  - embed_text()            — gemini-embedding-001 batch embeddings
  - retrieve_rag_context()  — embed query + pgvector cosine search
"""
import os
import time
import asyncio
import logging

from openai import OpenAI, RateLimitError, APITimeoutError, APIConnectionError
from sqlalchemy.orm import Session

logger = logging.getLogger("canvas.ai_gateway")

MODEL = os.getenv("GEMINI_MODEL")
EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL")
MIN_SPACING_S = float(os.getenv("GEMINI_MIN_SPACING_S"))
REQUEST_TIMEOUT_S = float(os.getenv("GEMINI_REQUEST_TIMEOUT_S"))
MAX_RETRIES = 3
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "5"))

_client: OpenAI | None = None
_lock = asyncio.Lock()
_last_dispatch_at = 0.0

# Lazy-initialised google-genai client for native features
_genai_client = None
_genai_lock = asyncio.Lock()


class QuotaExhausted(RuntimeError):
    """Raised when Gemini quota is exhausted or rate-limiting survives retries."""


# ── OpenAI-compat client ──────────────────────────────────────────────────────

def get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set — add it to backend/.env")
        _client = OpenAI(
            api_key=api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            timeout=REQUEST_TIMEOUT_S,
            max_retries=0,
        )
    return _client


def _is_daily_quota_error(err: Exception) -> bool:
    text = f"{getattr(err, 'message', '')} {getattr(err, 'body', '')}".lower()
    return any(k in text for k in ("per day", "daily", "quota exceeded", "quota_exceeded", "resource_exhausted"))


def _retry_after_seconds(err: Exception) -> float | None:
    response = getattr(err, "response", None)
    value = response.headers.get("retry-after") if response is not None else None
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


async def _wait_for_spacing() -> None:
    global _last_dispatch_at
    wait = MIN_SPACING_S - (time.monotonic() - _last_dispatch_at)
    if wait > 0:
        await asyncio.sleep(wait)
    _last_dispatch_at = time.monotonic()


async def generate_governed(**kwargs):
    """Drop-in for client.chat.completions.create(**kwargs), through the
    serialize/space/retry gateway."""
    client = get_client()

    async with _lock:
        await _wait_for_spacing()

        attempt = 0
        while True:
            attempt += 1
            try:
                return await asyncio.to_thread(client.chat.completions.create, **kwargs)
            except RateLimitError as e:
                if _is_daily_quota_error(e):
                    raise QuotaExhausted(
                        "Gemini's daily quota is used up — try again tomorrow or set a different GEMINI_API_KEY."
                    ) from e
                if attempt > MAX_RETRIES:
                    raise QuotaExhausted(
                        "Gemini keeps rate-limiting — wait a minute and try again."
                    ) from e
                backoff = _retry_after_seconds(e) or min(2 ** attempt, 20)
                logger.warning("Gemini rate-limited (attempt %d/%d), retrying in %.1fs", attempt, MAX_RETRIES, backoff)
                await asyncio.sleep(backoff)
                _last_dispatch_at = time.monotonic()
            except (APITimeoutError, APIConnectionError):
                if attempt > MAX_RETRIES:
                    raise
                logger.warning("Gemini connection failed (attempt %d/%d), retrying", attempt, MAX_RETRIES)
                await _wait_for_spacing()


# ── Native google-genai client (Search grounding + Embeddings) ────────────────

def _get_genai_client():
    """Lazy-init the google-genai SDK client."""
    global _genai_client
    if _genai_client is None:
        try:
            from google import genai  # type: ignore
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise RuntimeError("GEMINI_API_KEY is not set")
            _genai_client = genai.Client(api_key=api_key)
        except ImportError as exc:
            raise RuntimeError(
                "google-genai package not installed. Run: pip install google-genai"
            ) from exc
    return _genai_client


async def generate_with_search(query: str, context: str = "") -> tuple[str, list[dict]]:
    """Call Gemini with Google Search grounding (native SDK).

    Returns (summary_text, citations) where citations is a list of
    {title: str, url: str} dicts.
    """
    async with _genai_lock:
        prompt = query
        if context:
            prompt = f"{context}\n\nResearch query: {query}"

        def _call():
            client = _get_genai_client()
            from google.genai import types  # type: ignore
            response = client.models.generate_content(
                model=MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                ),
            )
            return response

        try:
            response = await asyncio.to_thread(_call)
        except Exception as e:
            logger.error("generate_with_search failed: %s", e)
            raise

        summary = ""
        if response.candidates:
            for part in response.candidates[0].content.parts:
                if hasattr(part, "text") and part.text:
                    summary += part.text

        citations: list[dict] = []
        try:
            grounding = response.candidates[0].grounding_metadata
            if grounding and grounding.grounding_chunks:
                for chunk in grounding.grounding_chunks:
                    if hasattr(chunk, "web") and chunk.web:
                        citations.append({
                            "title": chunk.web.title or "",
                            "url": chunk.web.uri or "",
                        })
        except (AttributeError, IndexError):
            pass

        return summary, citations


# ── Embeddings ────────────────────────────────────────────────────────────────

async def embed_text(texts: list[str]) -> list[list[float]]:
    """Batch embed texts using gemini-embedding-001 (768 dimensions).

    Returns a list of embedding vectors in the same order as the input.
    Processes in batches of 100 to stay within API limits.
    """
    if not texts:
        return []

    BATCH_SIZE = 100
    all_embeddings: list[list[float]] = []

    def _embed_batch(batch: list[str]) -> list[list[float]]:
        client = _get_genai_client()
        result = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=batch,
        )
        return [e.values for e in result.embeddings]

    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i: i + BATCH_SIZE]
        embeddings = await asyncio.to_thread(_embed_batch, batch)
        all_embeddings.extend(embeddings)

    return all_embeddings


# ── RAG retrieval ─────────────────────────────────────────────────────────────

async def retrieve_rag_context(
    db: Session,
    board_id: int,
    query: str,
    doc_names: list[str] | None = None,
    top_k: int | None = None,
):
    """Embed the query and run a pgvector cosine similarity search.

    Returns a list of DocumentChunk ORM objects ordered by relevance.
    """
    from . import crud as _crud  # avoid circular at module level

    k = top_k or RAG_TOP_K
    embeddings = await embed_text([query])
    if not embeddings:
        return []
    query_embedding = embeddings[0]
    return _crud.vector_search(
        db, board_id=board_id, query_embedding=query_embedding,
        top_k=k, doc_names=doc_names,
    )


# ── Board summary (async, used by main.py after each turn) ───────────────────

async def update_board_summary(db: Session, board_id: int, recent_messages: list[dict]) -> None:
    """Asynchronously regenerate and persist the board summary after a turn.
    Fires-and-forgets — caller should use asyncio.create_task()."""
    from . import crud as _crud

    snapshot = _crud.get_board_snapshot_text(db, board_id)
    conversation_tail = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in recent_messages[-6:]
    )
    prompt = (
        "You are summarising the state of a collaborative brainstorming board "
        "to serve as persistent memory for an AI agent.\n\n"
        f"## Recent conversation\n{conversation_tail}\n\n"
        f"## Current board contents\n{snapshot}\n\n"
        "Write a 3–5 sentence summary of the project, its key themes, decisions made so far, "
        "and any open questions. Be specific and dense — this is context, not a headline."
    )
    try:
        response = await generate_governed(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        summary = response.choices[0].message.content or ""
        _crud.upsert_board_summary(db, board_id, summary)
    except Exception as e:
        logger.warning("board summary update failed: %s", e)
