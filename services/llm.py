"""Single entry point for Gemini calls.

* maps the UI's model choice to a real model name
* fails fast on quota / availability errors and falls back to other models
* runs the blocking SDK in worker threads so the event loop stays free
"""
import asyncio
import time
from typing import AsyncGenerator, List, Optional

import google.generativeai as genai
from google.api_core import exceptions as gexc

from app.config import settings

# tried in order after the requested model when it is rate limited or unavailable
FALLBACK_MODELS = [
    "gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-flash-lite-latest", "gemini-3.1-flash-lite",
    "gemini-3.7-flash", "gemini-3.8-flash", "gemini-3.6-flash", "gemini-2.5-flash",
]
TRANSIENT = (gexc.ServiceUnavailable, gexc.DeadlineExceeded, gexc.InternalServerError)
RETRY_ROUNDS = 3  # extra passes over the model list when failures were temporary (503), not quota
RETRYABLE = (
    gexc.ResourceExhausted,
    gexc.ServiceUnavailable,
    gexc.DeadlineExceeded,
    gexc.InternalServerError,
    gexc.NotFound,
)
REQUEST_OPTIONS = {"timeout": 30, "retry": None}  # no hidden slow retries: we fall back instead

COOLDOWN_SECONDS = 45          # skip a model for a while after it was rate limited / down
MAX_CONCURRENT_CALLS = 3       # stay under per-minute request limits

_configured = False
_cooldown: dict = {}
_semaphore: Optional[asyncio.Semaphore] = None


def _sem() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(MAX_CONCURRENT_CALLS)
    return _semaphore


def _configure() -> None:
    global _configured
    if not _configured:
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        _configured = True


def resolve_model(choice: Optional[str]) -> str:
    """Map the UI's model id ('gemini-3-flash' / 'gemini-3-pro') to a real model name."""
    if choice and "pro" in choice.lower():
        return settings.GEMINI_PRO_MODEL
    return settings.GEMINI_MODEL


def candidate_models(primary: Optional[str] = None) -> List[str]:
    """Requested model first, then fallbacks; models that failed recently go last."""
    primary = primary or settings.GEMINI_MODEL
    ordered = [primary] + [m for m in FALLBACK_MODELS if m != primary]
    now = time.time()
    healthy = [m for m in ordered if _cooldown.get(m, 0) <= now]
    cooling = [m for m in ordered if _cooldown.get(m, 0) > now]
    return healthy + cooling


def _mark_failed(name: str, error: Exception) -> None:
    # a *daily* quota will not recover for hours, so stop trying that model for a while
    daily = "PerDay" in str(error)
    _cooldown[name] = time.time() + (3600 if daily else COOLDOWN_SECONDS)
    print(f"LLM: {name} unavailable ({type(error).__name__}), trying next model")


def _generate_sync(prompt: str, model_name: str, json_mode: bool) -> str:
    _configure()
    config = genai.types.GenerationConfig(response_mime_type="application/json") if json_mode else None
    response = genai.GenerativeModel(model_name).generate_content(
        prompt, generation_config=config, request_options=REQUEST_OPTIONS
    )
    return response.text


async def generate(prompt: str, json_mode: bool = False, model: Optional[str] = None) -> str:
    """One-shot generation with model fallback. Raises the last error if all fail."""
    loop = asyncio.get_running_loop()
    last: Optional[Exception] = None
    for attempt in range(RETRY_ROUNDS):
        transient = False
        for name in candidate_models(model):
            try:
                async with _sem():
                    return await loop.run_in_executor(None, lambda n=name: _generate_sync(prompt, n, json_mode))
            except RETRYABLE as e:
                _mark_failed(name, e)
                last = e
                transient = transient or isinstance(e, TRANSIENT)
        if not transient:
            break  # every model is out of quota: waiting a few seconds will not help
        await asyncio.sleep(2 * (attempt + 1))
    raise last or RuntimeError("No Gemini model available")


async def stream(prompt: str, model: Optional[str] = None) -> AsyncGenerator[str, None]:
    """Stream text pieces. Falls back to another model only if nothing was produced yet."""
    _configure()
    loop = asyncio.get_running_loop()
    last: Optional[Exception] = None

    for attempt in range(RETRY_ROUNDS):
        transient = False
        for name in candidate_models(model):
            queue: asyncio.Queue = asyncio.Queue()

            def worker(n: str = name, q: asyncio.Queue = queue):
                try:
                    for chunk in genai.GenerativeModel(n).generate_content(
                        prompt, stream=True, request_options=REQUEST_OPTIONS
                    ):
                        try:
                            text = chunk.text
                        except ValueError:  # blocked or empty chunk
                            text = ""
                        if text:
                            loop.call_soon_threadsafe(q.put_nowait, ("token", text))
                    loop.call_soon_threadsafe(q.put_nowait, ("done", None))
                except Exception as e:  # noqa: BLE001
                    loop.call_soon_threadsafe(q.put_nowait, ("error", e))

            loop.run_in_executor(None, worker)
            produced = False
            failed: Optional[Exception] = None
            while True:
                kind, value = await queue.get()
                if kind == "token":
                    produced = True
                    yield value
                elif kind == "error":
                    failed = value
                    break
                else:
                    break

            if failed is None:
                if not produced:
                    yield "I could not generate an answer for this question (the model returned no text)."
                return
            if produced or not isinstance(failed, RETRYABLE):
                raise failed
            _mark_failed(name, failed)
            last = failed
            transient = transient or isinstance(failed, TRANSIENT)
        if not transient:
            break
        await asyncio.sleep(2 * (attempt + 1))

    raise last or RuntimeError("No Gemini model available")
