"""The 3 golden demo questions for the VN utility agent — LIVE, opt-in.

These hit the deployed Vertex AI Agent Engine agent for real (Google Search
grounding included), so they need network, ADC, and the env var:

    UTILITY_AGENT_RESOURCE_NAME=projects/<num>/locations/<region>/reasoningEngines/<id> \
        uv run pytest -m manual tests/test_utility_agent_golden.py

Excluded from the default suite (`addopts = -m 'not integration and not manual'`).
Each question is asked in both Vietnamese and English; the answer must be
English, speakable, and not the failure fallback.
"""

import os

import pytest

from hub import utility_info

pytestmark = pytest.mark.manual

GOLDEN_QUESTIONS = [
    # 1. Current electricity price
    "Giá điện hiện tại là bao nhiêu?",
    "What is the current electricity price in Vietnam?",
    # 2. Upcoming water outages in Ho Chi Minh City
    "Sắp tới có lịch cúp nước ở thành phố Hồ Chí Minh không?",
    "Any upcoming water outages in Ho Chi Minh City?",
    # 3. Why is this month's bill higher (general tier explanation, not tenant-specific)
    "Tại sao hóa đơn điện tháng này cao hơn?",
    "Why is my electricity bill higher this month?",
]


@pytest.fixture(autouse=True)
def _require_configuration():
    if not os.environ.get(utility_info.AGENT_RESOURCE_ENV):
        pytest.skip(f"{utility_info.AGENT_RESOURCE_ENV} not set")
    utility_info._cache.clear()


@pytest.mark.parametrize("question", GOLDEN_QUESTIONS)
def test_golden_question_live(question: str):
    result = utility_info.ask_utility_info(question)
    answer = result["answer"]
    assert answer, "empty answer"
    assert answer != utility_info.FALLBACK_ANSWER, "live call fell back"
    assert answer != utility_info.NOT_CONFIGURED_ANSWER
    assert len(answer) <= utility_info.MAX_ANSWER_CHARS
    # English-only TTS downstream: the answer must not echo Vietnamese diacritics.
    assert answer == answer.encode("ascii", errors="ignore").decode(), (
        f"non-ASCII (likely Vietnamese) answer: {answer!r}"
    )
