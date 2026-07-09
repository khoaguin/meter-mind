"""LLM-inside seam — the ONE model call in the hub (Option A, no chat loop).

Provider-agnostic via litellm: set `LLM_MODEL` (in `.env`) to any litellm model
string and litellm reads that provider's key from the environment.
  anthropic/claude-opus-4-8  (default, best)   openai/gpt-4o
  gemini/gemini-1.5-flash                       ollama/llama3  (local, no key)
  huggingface/<repo>

Deterministic code decides there is a spike and computes `factor` / `detected_at`;
the model only writes the English sentence. Any SDK error, timeout, or missing key
falls back to a canned English string so beat #2 never hard-fails on a network blip
on stage. (English, not Vietnamese: Agora's voice track can't TTS Vietnamese yet.)
"""

import os

import litellm
from dotenv import load_dotenv
from loguru import logger

load_dotenv()  # pull LLM_MODEL + provider keys from .env (no-op if the file is absent)
litellm.telemetry = False  # no anonymous usage reporting

DEFAULT_MODEL = (
    "anthropic/claude-opus-4-8"  # best for this task; override with LLM_MODEL
)
MODEL = os.environ.get("LLM_MODEL", DEFAULT_MODEL)
_MAX_TOKENS = 200
_SYSTEM = (
    "You explain electricity and water usage for a rental-property manager. "
    "Write exactly ONE short, natural, friendly English sentence explaining the "
    "abnormal consumption. No greeting and no extra commentary."
)


def canned_en(kind: str, detected_at: str, factor: float) -> str:
    """Deterministic English fallback used when the LLM is unreachable (same shape as beat #2)."""
    return (
        f"Detected {kind}: usage rose about {factor:g} times on {detected_at} compared with "
        "normal days — likely a leak or a faulty meter."
    )


def explain_anomaly_en(
    device_id: str, kind: str, detected_at: str, factor: float
) -> str:
    """One-line English explanation from the LLM; fall back to a canned string on any error."""
    prompt = (
        f"Device {device_id} has a {kind}: usage on {detected_at} was about {factor:g} times the "
        "average of the other days this month. Briefly explain this to the manager and "
        "suggest a likely cause (leak / faulty meter)."
    )
    try:
        # litellm re-exports `completion` untyped, so pyrefly can't see it as callable.
        response = litellm.completion(  # type: ignore  # noqa: PGH003
            model=MODEL,
            max_tokens=_MAX_TOKENS,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": prompt},
            ],
        )
        content = response["choices"][0]["message"][
            "content"
        ]  # litellm normalizes across providers
        text = (content or "").strip()
        return text or canned_en(kind, detected_at, factor)
    except (
        Exception
    ) as exc:  # network / auth / bad-model / timeout — never hard-fail the demo
        logger.warning(
            "explain_anomaly_en: LLM unreachable ({}); using canned English", exc
        )
        return canned_en(kind, detected_at, factor)
