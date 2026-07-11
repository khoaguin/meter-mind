"""Unit tests for hub.utility_info — the ask_utility_info backend.

Everything here mocks the Agent Engine call; no network, no credentials. The
live golden-question suite lives in tests/test_utility_agent_golden.py and is
opt-in (`-m manual`).
"""

import time

import pytest

from hub import utility_info


@pytest.fixture(autouse=True)
def _clean_state(monkeypatch: pytest.MonkeyPatch):
    """Each test starts unconfigured, with an empty cache."""
    monkeypatch.delenv(utility_info.AGENT_RESOURCE_ENV, raising=False)
    monkeypatch.delenv(utility_info.CANNED_ANSWERS_ENV, raising=False)
    utility_info._cache.clear()
    yield
    utility_info._cache.clear()


RESOURCE = "projects/161661253262/locations/asia-southeast1/reasoningEngines/42"


def _configure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(utility_info.AGENT_RESOURCE_ENV, RESOURCE)


# --- normalization ---------------------------------------------------------


def test_normalize_folds_vietnamese_diacritics():
    assert (
        utility_info._normalize("Giá điện hiện tại là bao nhiêu?")
        == "gia dien hien tai la bao nhieu"
    )


def test_normalize_ignores_case_punctuation_whitespace():
    assert utility_info._normalize("  What is  THE price?! ") == "what is the price"


# --- truncation ------------------------------------------------------------


def test_truncate_keeps_short_answers_intact():
    assert utility_info._truncate_speakable("Short answer.") == "Short answer."


def test_truncate_folds_leaked_vietnamese_diacritics():
    out = utility_info._truncate_speakable("Parts of Bảy Hiền and Thủ Đức wards.")
    assert out == "Parts of Bay Hien and Thu Duc wards."


def test_truncate_cuts_at_sentence_boundary():
    long = "First sentence here. " * 30
    out = utility_info._truncate_speakable(long)
    assert len(out) <= utility_info.MAX_ANSWER_CHARS
    assert out.endswith("First sentence here.")


def test_truncate_single_giant_sentence_falls_back_to_word_boundary():
    out = utility_info._truncate_speakable("word " * 200)
    assert 0 < len(out) <= utility_info.MAX_ANSWER_CHARS
    assert not out.endswith(" ")


# --- unconfigured / failure / fallback paths --------------------------------


def test_unset_resource_name_returns_not_configured():
    result = utility_info.ask_utility_info("Giá điện hiện tại là bao nhiêu?")
    assert result["answer"] == utility_info.NOT_CONFIGURED_ANSWER
    assert result["as_of"]


def test_agent_exception_returns_speakable_fallback(monkeypatch: pytest.MonkeyPatch):
    _configure(monkeypatch)
    monkeypatch.setattr(
        utility_info,
        "_query_agent",
        lambda *_: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    result = utility_info.ask_utility_info("any question")
    assert result["answer"] == utility_info.FALLBACK_ANSWER


def test_timeout_is_hard_capped(monkeypatch: pytest.MonkeyPatch):
    _configure(monkeypatch)
    monkeypatch.setattr(utility_info, "AGENT_TIMEOUT_S", 0.2)

    def slow_agent(*_: object) -> str:
        time.sleep(2.0)
        return "too late"

    monkeypatch.setattr(utility_info, "_query_agent", slow_agent)
    t0 = time.monotonic()
    result = utility_info.ask_utility_info("slow question")
    elapsed = time.monotonic() - t0
    assert result["answer"] == utility_info.FALLBACK_ANSWER
    assert elapsed < 1.0  # returned at the cap, not after the 2 s sleep


def test_empty_answer_counts_as_failure(monkeypatch: pytest.MonkeyPatch):
    _configure(monkeypatch)
    monkeypatch.setattr(utility_info, "_query_agent", lambda *_: "")
    result = utility_info.ask_utility_info("question")
    assert result["answer"] == utility_info.FALLBACK_ANSWER


def test_canned_answer_used_only_on_failure(monkeypatch: pytest.MonkeyPatch):
    _configure(monkeypatch)
    monkeypatch.setenv(
        utility_info.CANNED_ANSWERS_ENV,
        '{"gia dien hien tai la bao nhieu": '
        '{"answer": "As of July 2026, about 2,204 dong per kilowatt hour.", '
        '"as_of": "2026-07-01"}}',
    )
    # Live call succeeds -> canned answer must NOT shadow it.
    monkeypatch.setattr(utility_info, "_query_agent", lambda *_: "Live answer.")
    ok = utility_info.ask_utility_info("Giá điện hiện tại là bao nhiêu?")
    assert ok["answer"] == "Live answer."

    # Live call fails -> the accented question matches the unaccented key.
    utility_info._cache.clear()
    monkeypatch.setattr(
        utility_info,
        "_query_agent",
        lambda *_: (_ for _ in ()).throw(TimeoutError()),
    )
    canned = utility_info.ask_utility_info("Giá điện hiện tại là bao nhiêu?")
    assert canned["answer"].startswith("As of July 2026")
    assert canned["as_of"] == "2026-07-01"


def test_canned_answers_accept_plain_strings(monkeypatch: pytest.MonkeyPatch):
    _configure(monkeypatch)
    monkeypatch.setenv(
        utility_info.CANNED_ANSWERS_ENV, '{"water outage hcmc": "No outages planned."}'
    )
    monkeypatch.setattr(
        utility_info,
        "_query_agent",
        lambda *_: (_ for _ in ()).throw(RuntimeError()),
    )
    result = utility_info.ask_utility_info("Water outage HCMC?")
    assert result["answer"] == "No outages planned."


def test_invalid_canned_json_still_returns_fallback(monkeypatch: pytest.MonkeyPatch):
    _configure(monkeypatch)
    monkeypatch.setenv(utility_info.CANNED_ANSWERS_ENV, "{not json")
    monkeypatch.setattr(
        utility_info,
        "_query_agent",
        lambda *_: (_ for _ in ()).throw(RuntimeError()),
    )
    result = utility_info.ask_utility_info("anything")
    assert result["answer"] == utility_info.FALLBACK_ANSWER


# --- cache -------------------------------------------------------------------


def test_cache_hit_skips_live_call(monkeypatch: pytest.MonkeyPatch):
    _configure(monkeypatch)
    calls = []

    def agent(*args: object) -> str:
        calls.append(args)
        return "Cached answer."

    monkeypatch.setattr(utility_info, "_query_agent", agent)
    first = utility_info.ask_utility_info("Giá điện hiện tại là bao nhiêu?")
    # Same question, different accents/punctuation -> same cache entry.
    second = utility_info.ask_utility_info("gia dien hien tai la bao nhieu")
    assert first == second
    assert len(calls) == 1


def test_cache_expires_after_ttl(monkeypatch: pytest.MonkeyPatch):
    _configure(monkeypatch)
    monkeypatch.setattr(utility_info, "_query_agent", lambda *_: "Answer one.")
    utility_info.ask_utility_info("q")
    key = utility_info._normalize("q")
    expiry, payload = utility_info._cache[key]
    utility_info._cache[key] = (time.monotonic() - 1, payload)  # force expiry
    monkeypatch.setattr(utility_info, "_query_agent", lambda *_: "Answer two.")
    assert utility_info.ask_utility_info("q")["answer"] == "Answer two."


def test_successful_answer_is_truncated_and_stamped(monkeypatch: pytest.MonkeyPatch):
    _configure(monkeypatch)
    monkeypatch.setattr(
        utility_info, "_query_agent", lambda *_: "A very fine sentence. " * 40
    )
    result = utility_info.ask_utility_info("q")
    assert len(result["answer"]) <= utility_info.MAX_ANSWER_CHARS
    assert result["answer"].endswith("sentence.")
    assert result["as_of"] == time.strftime("%Y-%m-%d", time.gmtime())


# --- event parsing -----------------------------------------------------------


def test_event_text_reads_model_parts_and_skips_partials():
    event = {
        "content": {"role": "model", "parts": [{"text": "Hello "}, {"text": "there."}]}
    }
    assert utility_info._event_text(event) == "Hello there."
    assert utility_info._event_text({**event, "partial": True}) == ""
    assert (
        utility_info._event_text(
            {"content": {"role": "user", "parts": [{"text": "x"}]}}
        )
        == ""
    )
    assert utility_info._event_text({}) == ""
