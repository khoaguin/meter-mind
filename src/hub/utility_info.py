"""`ask_utility_info` backend — the VN utility agent on Vertex AI Agent Engine.

The hub's five core tools are deterministic; this one is not. It forwards a
general Vietnam-utilities question (tariffs, outages, tier mechanics) to the
`vn_utility_agent` ADK agent deployed on Vertex AI Agent Engine, which answers
in voice-friendly English grounded in Google Search.

Demo-hardening, in order of application:
  1. In-memory cache (normalized question, 1 h TTL) — a repeated demo question
     never leaves the process.
  2. Hard 12 s cap on the live call (the My Bot MCP budget is 10–20 s total).
  3. On any failure: canned answers from `UTILITY_CANNED_ANSWERS_JSON`, else a
     fixed speakable apology. The voice bot always gets something to say.

Auth is Application Default Credentials only — on Cloud Run that's the runtime
service account (needs `roles/aiplatform.user`); no key files anywhere.
"""

import json
import os
import re
import threading
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import google.auth
import google.auth.transport.requests
import httpx
from loguru import logger

AGENT_RESOURCE_ENV = "UTILITY_AGENT_RESOURCE_NAME"
CANNED_ANSWERS_ENV = "UTILITY_CANNED_ANSWERS_JSON"

AGENT_TIMEOUT_S = 12.0
CACHE_TTL_S = 3600.0
MAX_ANSWER_CHARS = 350

FALLBACK_ANSWER = (
    "Sorry, I could not reach the utility information service just now. "
    "Please try again in a moment."
)
NOT_CONFIGURED_ANSWER = (
    "The utility information service is not set up on this server yet, "
    "so I cannot look that up right now."
)

# normalized question -> (monotonic expiry, result)
_cache: dict[str, tuple[float, dict[str, str]]] = {}
_cache_lock = threading.Lock()

_credentials: Any = None
_credentials_lock = threading.Lock()


def _today() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def _fold_diacritics(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    # Vietnamese đ/Đ doesn't decompose to "d" + combining mark.
    return stripped.replace("đ", "d").replace("Đ", "D")


def _normalize(question: str) -> str:
    """Cache/canned-answer key: diacritics stripped, casefolded, alphanumeric.

    Folding diacritics means canned-answer keys can be authored without
    Vietnamese input ("gia dien hien tai la bao nhieu") and still match the
    fully accented question the voice bot sends.
    """
    return re.sub(r"[^a-z0-9]+", " ", _fold_diacritics(question).casefold()).strip()


def _truncate_speakable(text: str, limit: int = MAX_ANSWER_CHARS) -> str:
    """Cut at a sentence boundary so the TTS never trails off mid-thought.

    Also folds diacritics the agent may leak in proper nouns ("Bảy Hiền" →
    "Bay Hien") — the downstream TTS is English-only and chokes on accents.
    """
    text = _fold_diacritics(text).strip()
    if len(text) <= limit:
        return text
    sentences = re.split(r"(?<=[.!?])\s+", text)
    out = ""
    for sentence in sentences:
        candidate = f"{out} {sentence}".strip()
        if len(candidate) > limit:
            break
        out = candidate
    return out or text[:limit].rsplit(" ", 1)[0]


def _access_token() -> str:
    global _credentials
    with _credentials_lock:
        if _credentials is None:
            _credentials, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
        if not _credentials.valid:
            _credentials.refresh(google.auth.transport.requests.Request())
        return _credentials.token


def _event_text(event: dict[str, Any]) -> str:
    content = event.get("content") or {}
    if content.get("role") != "model" or event.get("partial"):
        return ""
    return "".join(p.get("text") or "" for p in content.get("parts") or [])


def _query_agent(resource_name: str, question: str) -> str:
    """One `streamQuery` call against Agent Engine; returns the final answer text.

    The response body is newline-delimited JSON ADK events; a single event may
    span lines, so lines are buffered until they parse. The last model-text
    event is the agent's final answer.
    """
    region = resource_name.split("/locations/")[1].split("/")[0]
    url = f"https://{region}-aiplatform.googleapis.com/v1/{resource_name}:streamQuery"
    body = {
        "class_method": "stream_query",
        "input": {"user_id": "meter-mind-hub", "message": question},
    }
    headers = {"Authorization": f"Bearer {_access_token()}"}
    deadline = time.monotonic() + AGENT_TIMEOUT_S
    answer = ""
    buffer = ""
    timeout = httpx.Timeout(AGENT_TIMEOUT_S, connect=3.0)
    with (
        httpx.Client(timeout=timeout) as client,
        client.stream("POST", url, json=body, headers=headers) as response,
    ):
        response.raise_for_status()
        for line in response.iter_lines():
            if time.monotonic() > deadline:
                raise TimeoutError("agent stream exceeded the 12 s budget")
            buffer += line
            try:
                event = json.loads(buffer)
            except ValueError:
                continue  # incomplete event — keep buffering
            buffer = ""
            if text := _event_text(event):
                answer = text
    return answer.strip()


def _canned_answer(key: str) -> dict[str, str] | None:
    raw = os.environ.get(CANNED_ANSWERS_ENV, "").strip()
    if not raw:
        return None
    try:
        mapping = json.loads(raw)
    except ValueError:
        logger.warning("{} is not valid JSON — ignoring", CANNED_ANSWERS_ENV)
        return None
    for canned_question, value in mapping.items():
        if _normalize(canned_question) != key:
            continue
        if isinstance(value, dict):
            answer = str(value.get("answer", "")).strip()
            as_of = str(value.get("as_of", "")).strip() or _today()
        else:
            answer, as_of = str(value).strip(), _today()
        if answer:
            return {"answer": _truncate_speakable(answer), "as_of": as_of}
    return None


def ask_utility_info(question: str) -> dict[str, str]:
    """Answer a general VN-utilities question; always returns something speakable."""
    key = _normalize(question)
    now = time.monotonic()
    with _cache_lock:
        hit = _cache.get(key)
        if hit and hit[0] > now:
            return dict(hit[1])

    resource_name = os.environ.get(AGENT_RESOURCE_ENV, "").strip()
    if not resource_name:
        logger.warning(
            "{} unset — ask_utility_info is not configured", AGENT_RESOURCE_ENV
        )
        return {"answer": NOT_CONFIGURED_ANSWER, "as_of": _today()}

    # A `with` block would join the worker on exit, defeating the hard cap —
    # shut down without waiting instead; httpx's own timeouts reap the
    # abandoned thread shortly after rather than leaking it.
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        future = pool.submit(_query_agent, resource_name, question)
        answer = future.result(timeout=AGENT_TIMEOUT_S)
        if not answer:
            raise RuntimeError("agent returned an empty answer")
    except Exception as exc:  # noqa: BLE001 — must never crash the voice call
        logger.warning("ask_utility_info live call failed: {!r}", exc)
        if canned := _canned_answer(key):
            return canned
        return {"answer": FALLBACK_ANSWER, "as_of": _today()}
    finally:
        pool.shutdown(wait=False, cancel_futures=True)

    result = {"answer": _truncate_speakable(answer), "as_of": _today()}
    with _cache_lock:
        _cache[key] = (now + CACHE_TTL_S, dict(result))
    return result
