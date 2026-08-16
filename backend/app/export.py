"""
Google Docs export pipeline for Skretch.

Flow:
  1. Receive board_id + structured payload from the frontend.
  2. Build a rich AI prompt from the payload (frames, stickies, reactions, citations).
  3. Call Gemini to generate a structured document spec as JSON.
  4. Create a Google Doc via the Docs REST API using the user's OAuth access token.
  5. Apply all content + formatting via batchUpdate (headings, paragraphs, citation markers).
  6. Return {doc_url, doc_id, title}.
"""

import asyncio
import json
import logging
import os
import re
import time

import httpx
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from . import ai_gateway, models

logger = logging.getLogger("canvas.export")

GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
DOCS_API             = "https://docs.googleapis.com/v1/documents"
OAUTH_TOKEN_URL      = "https://oauth2.googleapis.com/token"

# batchUpdate requests are chunked to stay well under Google's per-call limits
BATCH_CHUNK_SIZE = 300
# Retries for transient (429/5xx) failures against the Docs API
DOCS_API_MAX_RETRIES = 3
DOCS_API_RETRY_BASE_DELAY = 1.5


# ─────────────────────────── Token management ────────────────────────────────

async def ensure_fresh_token(user: models.User, db: Session) -> str:
    """Return a valid Google access token, refreshing via refresh_token if needed."""
    if not user.google_access_token:
        raise ValueError(
            "No Google access token stored. Please sign out and sign back in "
            "to grant Google suite access."
        )
    # Still fresh (> 60 s until expiry) — use as-is
    if user.google_token_expiry and time.time() < user.google_token_expiry - 60:
        return user.google_access_token
    # Need to refresh
    if not user.google_refresh_token:
        raise ValueError(
            "Access token expired and no refresh token is available. "
            "Please sign out and sign back in."
        )
    async with httpx.AsyncClient() as client:
        r = await client.post(
            OAUTH_TOKEN_URL,
            data={
                "client_id":     GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "refresh_token": user.google_refresh_token,
                "grant_type":    "refresh_token",
            },
        )
        r.raise_for_status()
        tok = r.json()

    user.google_access_token = tok["access_token"]
    user.google_token_expiry = time.time() + tok.get("expires_in", 3600)
    db.commit()
    return user.google_access_token


# ─────────────────────────── AI document generation ──────────────────────────

_EXPORT_SYSTEM = """\
You are an expert analyst and technical writer. You receive the JSON snapshot \
of a digital brainstorming whiteboard and produce a polished, publication-ready document.

STRICT RULES — violating any of these is a failure:
1. Output ONLY a single valid JSON object — NO markdown fences, NO text outside the JSON.
2. EVERY citation that appears in any sticky's data.citations array MUST be referenced \
   as [N] somewhere in the body text AND listed in the references array. This is mandatory.
3. DO NOT invent or fabricate citations. Only use those explicitly present in the board data.
4. Synthesise sticky content into coherent prose paragraphs — never just list raw quotes.
5. Stickies with more reactions (especially 🔥) are high-priority insights — give them \
   prominent placement and more prose coverage.
6. Frames ordered left→right on the canvas implies sequence or priority — reflect this ordering.
7. The document must stand alone as professional reading without access to the board.
8. Every section must be substantive — at least 2 paragraphs of analysis, not summaries.

OUTPUT SCHEMA (strict — all fields required):
{
  "title": "<compelling, specific document title>",
  "format": "essay" | "prd",
  "abstract": "<2–4 sentences: what this covers and the key conclusion or recommendation>",
  "sections": [
    {
      "heading": "<section title>",
      "level": 1,
      "paragraphs": [
        "<coherent prose; cite sources inline as [N] or [N, M]>"
      ],
      "subsections": [
        { "heading": "...", "level": 2, "paragraphs": ["..."] }
      ]
    }
  ],
  "references": [
    { "number": 1, "title": "<source name>", "url": "<https://...>" }
  ]
}

FORMAT SELECTION:
- "essay"  → research findings, analysis, strategy, exploration, retrospectives
- "prd"    → features, requirements, user stories, technical specs, product decisions

PRD section structure:
  Overview → Goals & Success Metrics → User Stories → Requirements →
  Technical Considerations → Open Questions

Essay section structure:
  Introduction → [Thematic sections derived from frames] → Analysis & Implications → Conclusion
"""


# ─────────────────────────── Doc spec schema ──────────────────────────────
#
# The model is instructed to emit this shape, but instructions alone don't
# guarantee it — we validate against this schema and retry on failure rather
# than letting a malformed field (e.g. `references` as a dict, a missing
# `heading`) blow up deep inside request-building with a raw KeyError/500.

class DocSection(BaseModel):
    heading: str = ""
    level: int = 1
    paragraphs: list[str] = []
    subsections: list["DocSection"] = []


DocSection.model_rebuild()


class DocReference(BaseModel):
    number: int
    title: str = ""
    url: str = ""


class DocSpec(BaseModel):
    title: str = ""
    format: str = "essay"
    abstract: str = ""
    sections: list[DocSection] = []
    references: list[DocReference] = []


def _payload_to_prompt(payload: dict, fmt_hint: str) -> str:
    hint = (
        f"\nThe user has specifically requested **{fmt_hint.upper()}** format.\n"
        if fmt_hint != "auto"
        else ""
    )
    return (
        f"Convert the following whiteboard snapshot into a document.{hint}\n\n"
        f"WHITEBOARD DATA:\n{json.dumps(payload, indent=2, ensure_ascii=False)}"
    )


async def _generate_doc_spec(payload: dict, fmt_hint: str = "auto", max_attempts: int = 2) -> DocSpec:
    """Ask Gemini to produce a structured document spec from the board payload.

    Validates the response against DocSpec and retries once (with the
    validation error fed back to the model) before giving up — this is the
    difference between a malformed field crashing deep inside
    _spec_to_requests vs. failing cleanly with a clear error.
    """
    messages = [
        {"role": "system", "content": _EXPORT_SYSTEM},
        {"role": "user",   "content": _payload_to_prompt(payload, fmt_hint)},
    ]

    raw = "{}"
    last_err: Exception | None = None

    for attempt in range(max_attempts):
        response = await ai_gateway.generate_governed(
            model=ai_gateway.MODEL,
            messages=messages,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or "{}"
        # Strip any accidental markdown fences
        raw = re.sub(r"```[a-z]*\n?|```", "", raw).strip()

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as e:
            last_err = e
            logger.warning("doc spec attempt %d: non-JSON response: %s", attempt, e)
            messages.append({"role": "assistant", "content": raw})
            messages.append({
                "role": "user",
                "content": f"That was not valid JSON ({e}). Return ONLY the JSON object, no fences, no prose.",
            })
            continue

        try:
            return DocSpec.model_validate(parsed)
        except ValidationError as e:
            last_err = e
            logger.warning("doc spec attempt %d: schema validation failed: %s", attempt, e)
            messages.append({"role": "assistant", "content": raw})
            messages.append({
                "role": "user",
                "content": f"That JSON didn't match the required schema: {e}. Return corrected JSON only.",
            })

    logger.error("AI returned invalid doc spec after %d attempts:\n%s", max_attempts, raw[:800])
    raise ValueError(f"AI did not return a valid document spec: {last_err}")


# ─────────────────────────── Google Docs builder ─────────────────────────────

class _DocBuilder:
    """
    Accumulates Google Docs API batchUpdate requests sequentially.

    Because batchUpdate applies requests in order, we can track `self.cur`
    (current end-of-body index) and always insert at that position.  Style
    requests follow immediately after their insertText and reference the
    correct indices because prior inserts have already executed in the batch.
    """

    _CITE_RE = re.compile(r"(\[\d+(?:,\s*\d+)*\])")

    def __init__(self):
        self.requests: list[dict] = []
        self.cur = 1  # Google Docs body always starts at index 1

    # ── internal ──────────────────────────────────────────────────────────

    @staticmethod
    def _ulen(s: str) -> int:
        """UTF-16 code-unit length — what the Docs API uses for index math."""
        return len(s.encode("utf-16-le")) // 2

    def _insert(self, text: str) -> tuple[int, int]:
        s = self.cur
        e = s + self._ulen(text)
        self.requests.append({
            "insertText": {"location": {"index": s}, "text": text}
        })
        self.cur = e
        return s, e

    def _para_style(self, s: int, e: int, named: str) -> None:
        self.requests.append({
            "updateParagraphStyle": {
                "range": {"startIndex": s, "endIndex": e},
                "paragraphStyle": {"namedStyleType": named},
                "fields": "namedStyleType",
            }
        })

    def _text_style(self, s: int, e: int, style: dict, fields: str) -> None:
        self.requests.append({
            "updateTextStyle": {
                "range": {"startIndex": s, "endIndex": e},
                "textStyle": style,
                "fields": fields,
            }
        })

    # ── public builders ───────────────────────────────────────────────────

    def heading(self, text: str, level: int = 1) -> "_DocBuilder":
        full = text.strip() + "\n"
        s, e = self._insert(full)
        self._para_style(s, e, f"HEADING_{min(max(level, 1), 6)}")
        return self

    def paragraph(self, text: str) -> "_DocBuilder":
        """Insert prose; bold + blue [N] citation markers."""
        parts = self._CITE_RE.split(text.strip())
        for part in parts:
            if not part:
                continue
            s, e = self._insert(part)
            if self._CITE_RE.fullmatch(part):
                self._text_style(
                    s, e,
                    style={
                        "bold": True,
                        "foregroundColor": {
                            "color": {
                                "rgbColor": {
                                    "red": 0.18, "green": 0.37, "blue": 0.88
                                }
                            }
                        },
                    },
                    fields="bold,foregroundColor",
                )
        self._insert("\n")
        return self

    def reference_line(self, number: int, title: str, url: str) -> "_DocBuilder":
        """[N] Title — title is a hyperlink."""
        self._insert(f"[{number}] ")
        s_t, e_t = self._insert(title or url)
        if url:
            self._text_style(
                s_t, e_t,
                style={"link": {"url": url}},
                fields="link",
            )
        self._insert("\n")
        return self

    def spacer(self) -> "_DocBuilder":
        self._insert("\n")
        return self

    def build(self) -> list[dict]:
        return self.requests


_CITE_NUM_RE = re.compile(r"\[(\d+(?:,\s*\d+)*)\]")


def _validate_citations(spec: DocSpec) -> None:
    """Cross-check inline [N] markers against the references list.

    The model is prompted not to invent citations, but that's a soft
    guarantee — log a warning on mismatch rather than trusting the prompt
    alone, since numbering drifts under load. This doesn't block export;
    it's a signal to watch in logs.
    """
    ref_numbers = {r.number for r in spec.references}

    cited_numbers: set[int] = set()

    def _scan(paragraphs: list[str]) -> None:
        for p in paragraphs:
            for match in _CITE_NUM_RE.findall(p):
                for n in match.split(","):
                    cited_numbers.add(int(n.strip()))

    def _walk(sections: list[DocSection]) -> None:
        for s in sections:
            _scan(s.paragraphs)
            _walk(s.subsections)

    _walk(spec.sections)

    missing_refs = cited_numbers - ref_numbers
    unused_refs = ref_numbers - cited_numbers
    if missing_refs:
        logger.warning(
            "doc spec cites [%s] with no matching reference entry",
            ", ".join(str(n) for n in sorted(missing_refs)),
        )
    if unused_refs:
        logger.warning(
            "doc spec has unused references not cited in body: %s",
            ", ".join(str(n) for n in sorted(unused_refs)),
        )


def _spec_to_requests(spec: DocSpec) -> list[dict]:
    """Convert the validated document spec into a flat list of Docs API requests."""
    b = _DocBuilder()

    abstract = (spec.abstract or "").strip()
    if abstract:
        b.heading("Abstract", level=1).paragraph(abstract).spacer()

    def _write_section(section: DocSection, level: int) -> None:
        b.heading(section.heading, level=level)
        for para in section.paragraphs:
            if para:
                b.paragraph(para)
        for sub in section.subsections:
            sub_level = max(level + 1, sub.level or level + 1)
            _write_section(sub, sub_level)

    for section in spec.sections:
        _write_section(section, max(1, section.level or 1))
        b.spacer()

    if spec.references:
        b.heading("References", level=1)
        for ref in sorted(spec.references, key=lambda r: r.number):
            b.reference_line(ref.number, ref.title, ref.url)

    return b.build()


# ─────────────────────────── Google Docs REST calls ──────────────────────────

def _is_retryable(status_code: int) -> bool:
    return status_code == 429 or status_code >= 500


async def _post_with_retry(client: httpx.AsyncClient, url: str, headers: dict, json_body: dict) -> httpx.Response:
    """POST with retry/backoff on 429 and 5xx. Raises on final failure."""
    last_exc: Exception | None = None
    for attempt in range(DOCS_API_MAX_RETRIES):
        try:
            r = await client.post(url, headers=headers, json=json_body)
        except httpx.TransportError as e:
            last_exc = e
            delay = DOCS_API_RETRY_BASE_DELAY * (2 ** attempt)
            logger.warning("Docs API transport error (attempt %d): %s — retrying in %.1fs", attempt, e, delay)
            await asyncio.sleep(delay)
            continue

        if r.is_success:
            return r
        if not _is_retryable(r.status_code) or attempt == DOCS_API_MAX_RETRIES - 1:
            logger.error("Docs API call failed %d: %s", r.status_code, r.text[:400])
            r.raise_for_status()
        delay = DOCS_API_RETRY_BASE_DELAY * (2 ** attempt)
        logger.warning("Docs API %d (attempt %d) — retrying in %.1fs", r.status_code, attempt, delay)
        await asyncio.sleep(delay)

    # Only reached if every attempt raised a TransportError
    raise last_exc or RuntimeError("Docs API call failed after retries")


async def _create_doc(access_token: str, title: str) -> str:
    """Create an empty Google Doc; return its documentId."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await _post_with_retry(
            client, DOCS_API,
            headers={"Authorization": f"Bearer {access_token}"},
            json_body={"title": title},
        )
        return r.json()["documentId"]


async def _batch_update(access_token: str, doc_id: str, requests: list[dict],
                         chunk_size: int = BATCH_CHUNK_SIZE) -> None:
    """Apply batchUpdate requests to an existing Google Doc, chunked to stay
    under Google's per-call request limits, with retry on transient failures.

    Note: requests within a chunk rely on prior inserts in the SAME batch
    having already shifted indices — that's still true within a chunk since
    we don't split mid-section. Chunk boundaries are safe because every
    index in `requests` was computed once against the full final document,
    and Docs applies each batchUpdate call's requests in order before the
    next call starts, so cross-chunk indices remain correct as long as
    chunks are sent strictly in order.
    """
    if not requests:
        return
    async with httpx.AsyncClient(timeout=90.0) as client:
        for i in range(0, len(requests), chunk_size):
            chunk = requests[i:i + chunk_size]
            await _post_with_retry(
                client, f"{DOCS_API}/{doc_id}:batchUpdate",
                headers={"Authorization": f"Bearer {access_token}"},
                json_body={"requests": chunk},
            )


# ─────────────────────────── Public entry point ───────────────────────────────

async def export_board_to_docs(
    user: models.User,
    db: Session,
    board_id: int,
    payload: dict,
    fmt_hint: str = "auto",
) -> dict:
    """
    Full export pipeline — returns {doc_url, doc_id, title}.

    Steps:
      1. Validate / refresh the user's Google access token.
      2. Ask Gemini to generate a structured document spec from the board.
      3. Create a Google Doc (empty) and apply content + formatting.
    """
    token = await ensure_fresh_token(user, db)

    logger.info("Generating doc spec for board %s (format=%s)", board_id, fmt_hint)
    spec = await _generate_doc_spec(payload, fmt_hint)
    _validate_citations(spec)

    title = spec.title.strip() or payload.get("board", "Skretch Export")
    logger.info("Creating Google Doc: %r", title)
    doc_id = await _create_doc(token, title)

    api_requests = _spec_to_requests(spec)
    logger.info("Applying %d Docs API requests to doc %s", len(api_requests), doc_id)
    await _batch_update(token, doc_id, api_requests)

    doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"
    logger.info("Export complete → %s", doc_url)
    return {"doc_url": doc_url, "doc_id": doc_id, "title": title}