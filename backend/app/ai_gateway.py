"""
Governed Gemini gateway — the single choke point every Gemini call goes
through. 
  1. SERIALIZE — every call shares one asyncio.Lock, so concurrent chat
     sessions (multiple tabs/users) never burst multiple requests at once.
  2. SPACE — consecutive calls are spaced by GEMINI_MIN_SPACING_S to stay
     under the free tier's per-minute request limit. The wait is computed
     from when the previous call was *dispatched*, not when it finished, so
     spacing is correct regardless of how long a call takes.
  3. RETRY — 429s are classified: a per-minute rate limit is retried with
     backoff (honoring a Retry-After header when present); a daily/quota
     error fails fast with a clear message instead of burning retries on
     something that won't recover within the request.

The original pattern this is adapted from also does cross-process pacing via
a shared DB table, for a case where a separate cron process shares the same
quota as the live server. This app is single-process — nothing else calls
Gemini — so that piece is intentionally left out. If a background worker is
ever added here, that's the extension point.
"""
import os
import time
import asyncio
import logging

from openai import OpenAI, RateLimitError, APITimeoutError, APIConnectionError

logger = logging.getLogger("canvas.ai_gateway")

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
MIN_SPACING_S = float(os.getenv("GEMINI_MIN_SPACING_S", "4"))
REQUEST_TIMEOUT_S = float(os.getenv("GEMINI_REQUEST_TIMEOUT_S", "30"))
MAX_RETRIES = 3

_client: OpenAI | None = None
_lock = asyncio.Lock()
_last_dispatch_at = 0.0


class QuotaExhausted(RuntimeError):
    """Raised when Gemini's quota is exhausted (daily) or a rate limit
    survives every retry — the caller should show this to the user rather
    than treat it as an unexpected error."""


def get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set — add it to backend/.env")
        _client = OpenAI(
            api_key=api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            # Explicit timeout instead of the SDK's longer default, and
            # max_retries=0 to disable its hidden internal retry — this
            # gateway is the only thing that should retry a call.
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
    """Drop-in for client.chat.completions.create(**kwargs), routed through
    the serialize/space/retry gateway above."""
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
                        "Gemini's daily quota is used up for this key — try again tomorrow, "
                        "or set a different GEMINI_API_KEY in backend/.env."
                    ) from e
                if attempt > MAX_RETRIES:
                    raise QuotaExhausted(
                        "Gemini keeps rate-limiting this key even after retrying — wait a minute and try again."
                    ) from e
                backoff = _retry_after_seconds(e) or min(2 ** attempt, 20)
                logger.warning("Gemini rate-limited (attempt %d/%d), retrying in %.1fs", attempt, MAX_RETRIES, backoff)
                await asyncio.sleep(backoff)
                _last_dispatch_at = time.monotonic()
            except (APITimeoutError, APIConnectionError):
                if attempt > MAX_RETRIES:
                    raise
                logger.warning("Gemini call failed to connect (attempt %d/%d), retrying", attempt, MAX_RETRIES)
                await _wait_for_spacing()
