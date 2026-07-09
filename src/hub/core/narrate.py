"""Claude-inside seam — the ONE model call in the hub (Option A, no chat loop).

Deterministic code decides there is a spike and computes `factor` / `detected_at`;
Claude only writes the plain-language Vietnamese sentence. Any SDK error, timeout,
or missing key falls back to a canned VN string so beat #2 never hard-fails on a
network blip on stage.
"""

import anthropic
from loguru import logger

MODEL = "claude-opus-4-8"
_MAX_TOKENS = 200
_SYSTEM = (
    "Bạn là trợ lý giải thích hóa đơn điện/nước cho quản lý nhà trọ ở Việt Nam. "
    "Viết đúng MỘT câu tiếng Việt ngắn gọn, tự nhiên, thân thiện giải thích mức "
    "tiêu thụ bất thường. Không thêm lời chào hay giải thích thừa."
)


def canned_vi(kind: str, detected_at: str, factor: float) -> str:
    """Deterministic VN fallback used when Claude is unreachable (same shape as beat #2)."""
    return (
        f"Phát hiện {kind}: mức tiêu thụ tăng khoảng {factor:g} lần vào {detected_at} "
        "so với mức thường ngày — nghi rò rỉ hoặc thiết bị lỗi."
    )


def explain_anomaly_vi(
    device_id: str, kind: str, detected_at: str, factor: float
) -> str:
    """One-line VN explanation from Claude; fall back to a canned string on any error."""
    prompt = (
        f"Thiết bị {device_id} có {kind}: mức tiêu thụ ngày {detected_at} cao gấp "
        f"khoảng {factor:g} lần mức trung bình các ngày khác trong tháng. "
        "Giải thích ngắn gọn cho quản lý và gợi ý nguyên nhân (rò rỉ / thiết bị lỗi)."
    )
    try:
        client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
        response = client.messages.create(
            model=MODEL,
            max_tokens=_MAX_TOKENS,
            system=_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        text = next(
            (
                getattr(block, "text", "")
                for block in response.content
                if block.type == "text"
            ),
            "",
        ).strip()
        return text or canned_vi(kind, detected_at, factor)
    except Exception as exc:  # network / auth / timeout — never hard-fail the demo
        logger.warning(
            "explain_anomaly_vi: Claude unreachable ({}); using canned VN", exc
        )
        return canned_vi(kind, detected_at, factor)
