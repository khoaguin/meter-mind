# Plan hiện thực — Track của Khoi (luuthaiminhkhoi)

> **Đã tạo trên GitHub** (label `dev-b`, assignee luuthaiminhkhoi, đều nằm trong project board):
> Phase 0 → Epic [#17](https://github.com/khoaguin/meter-mind/issues/17) (subs #25–29, M0) · Phase 1 → Epic [#18](https://github.com/khoaguin/meter-mind/issues/18) (subs #30–34, M3) · Phase 2 → Epic [#19](https://github.com/khoaguin/meter-mind/issues/19) (subs #35–39, M4) · Phase 3 → Epic [#21](https://github.com/khoaguin/meter-mind/issues/21) (subs #22–24, M4) · Phase 4 → Epic [#20](https://github.com/khoaguin/meter-mind/issues/20) (subs #40–42, M5)

> Nguồn: [GitHub Project "meter mind"](https://github.com/users/khoaguin/projects/4), lọc `assignee:luuthaiminhkhoi` (5 task, đều ở Todo) + `docs/arch.md`.

## Các task được giao

| # | Task | Mô tả trên board |
|---|------|------------------|
| 1 | **Agora spike** — Agora Agent + MCP + VN voice check | (không có mô tả — đây là spike Day-1 trong arch.md) |
| 2 | **[Hub] MCP server** wrapping Core/Agent tools | Thin MCP wrapper exposing the same tools for the voice box |
| 3 | **[Edge] Owner Dashboard** | Dashboard for analytics / detailed numbers / reports / history |
| 4 | **[Edge] Voice Box** — Agora S3 + My Bot + MCP | Flash Agora ESP32-S3, set My Bot persona, point at MCP endpoints, tune VN/EN. DONE = owner hỏi bằng giọng nói, chip trả lời bằng giọng nói |
| 5 | **[Edge] Real Edge Fleet** — jomjol chip → MQTT *(deprioritized)* | Thay sim bằng ESP32-CAM thật publish qua MQTT đúng contract. DONE = reading từ chip thật vào Hub DB |

**Phụ thuộc vào Khoa (khoaguin):** Core API contract freeze + seed data freeze + stub REST/MCP endpoint (đang In Progress), sau đó SQLite schema, Core tools, Agent. Mọi thứ của Khoi đều bám vào **Core API seam** — chỉ cần contract freeze là hai người làm song song, zero shared state.

---

## Phase 0 — Spike & khử rủi ro (Day 1) → Task #1

Mục tiêu: trả lời **câu hỏi rủi ro duy nhất** trước khi build gì thêm.

1. Xác nhận **My Bot (Agora Conversational AI) có nhận custom MCP server không** — đọc docs, hỏi mentor Agora / Discord của AABW.
2. Xác nhận **có giọng tiếng Việt** (ASR + TTS) trong My Bot; nếu không → fallback EN hoặc TTS provider khác qua Agora.
3. Dựng account Agora + tạo project, chạy demo My Bot mặc định trên ESP32-S3 (chưa cần tool nào).
4. Trỏ My Bot vào **stub MCP endpoint** của Khoa (fake data) → gọi được 1 tool và nghe chip đọc kết quả.

**Exit criteria:** chip nói được 1 câu trả lời lấy từ stub MCP. Nếu bước 1/2 fail → báo ngay để đổi kiến trúc (vd. dùng REST webhook thay MCP) khi còn Day 1.

Phối hợp Day 1 (cả hai): chốt **Core API contract** (tên tool, args, JSON I/O) và **seed data** — Khoi review từ góc độ "câu nào owner sẽ hỏi bằng giọng nói".

## Phase 1 — MCP server bọc Core/Agent tools (Day 2 sáng) → Task #2

Chặn bởi: Core API contract freeze (xong Day 1). Không chờ Core code thật — build trên contract, swap implementation sau.

1. Scaffold MCP server Python (FastMCP hoặc SDK chính thức) trong repo, ví dụ `src/hub/mcp_server.py`.
2. Expose đúng bộ tool đã freeze (dự kiến: `get_latest_readings`, `get_unpaid_tenants`, `compute_bill`, `explain_anomaly`, `draft_reminder`, P1: `request_recapture`). Tên + schema **y hệt** contract — đây là seam.
3. Transport: HTTP/SSE để My Bot gọi qua mạng (chip không chạy stdio). Bind vào LAN, ghi rõ URL + tool docs cho chính mình dùng ở Phase 2.
4. Ban đầu trả fake data (tái dùng stub của Khoa), khi Core của Khoa xong thì đổi import — không đổi schema.
5. Test: gọi từng tool bằng MCP inspector / curl; viết tool docs ngắn (1 dòng/tool).

**Exit criteria:** mọi tool trong contract gọi được qua HTTP, trả JSON đúng schema.

## Phase 2 — Voice Box end-to-end (Day 2 chiều → Day 3) → Task #4

Chặn bởi: Phase 1 (MCP endpoint chạy).

1. Flash firmware Agora Conv-AI lên ESP32-S3, cấu hình WiFi cùng LAN với Hub.
2. Set **My Bot persona**: chủ trọ hỏi về điện nước — system prompt tiếng Việt, mô tả 5 demo beats (ai chưa đóng tiền, kiosk nào rò rỉ, hoá đơn tháng này…).
3. Trỏ persona vào MCP endpoint của Phase 1, bật đủ tools.
4. Tune hội thoại VN/EN: độ dài câu trả lời TTS, số đọc đúng (11.234 m³), latency chấp nhận được.
5. Chạy đủ 5 demo beats bằng giọng nói; ghi lại câu hỏi "chuẩn" cho demo script.
6. P1 nếu kịp: beat "act" — `request_recapture` (nói → agent → fleet đọc lại).

**Exit criteria (DONE của task):** owner hỏi bằng giọng nói → chip nói lại đáp án tính từ dữ liệu thật trong Hub DB.

## Phase 3 — Owner Dashboard (Day 3, song song lúc chờ tune voice) → Task #3

Chặn bởi: REST của Core (Khoa). Đây là **backup demo-safe** nếu voice/network chết trên sân khấu — phải xong trước rehearsal.

1. Trang read-only duy nhất, tối giản (FastAPI + Jinja/HTMX hoặc 1 file HTML gọi REST): devices · latest reads · paid/unpaid · cảnh báo leak/low-confidence.
2. Thêm phần history/analytics đơn giản (bảng readings theo ngày, tổng tiêu thụ) — đúng mô tả "analytics / detailed numbers / reports / history".
3. Auto-refresh vài giây để demo "live" khi bật MQTT ingest.

**Exit criteria:** 5 demo beats đọc được từ dashboard mà không cần voice.

## Phase 4 — Real jomjol chip (stretch, sau rehearsal) → Task #5

Deprioritized — chỉ làm khi Phase 0–3 xong và demo đã rehearse.

1. Flash jomjol AI-on-the-edge lên ESP32-CAM, chỉnh MQTT về broker của Hub, `MainTopic` theo contract.
2. Kiểm tra bằng test contract sẵn có (`tests/test_contract.py` là spec): topics + `/json` body khớp; nhớ tolerance rules (additive topics optional, `error` là free text).
3. **Exit criteria:** reading từ chip thật xuất hiện trong Hub DB, dashboard hiển thị — không sửa gì ở downstream.

---

## Thứ tự & phụ thuộc

```
Day 1: Phase 0 (spike) ──┐  + cùng Khoa freeze contract & seed
Day 2: Phase 1 (MCP) ────┴→ Phase 2 (Voice e2e)
Day 3: Phase 3 (Dashboard, song song) → integrate + rehearse → Phase 4 (nếu dư thời gian)
```

Nguyên tắc: **contract là seam** — mọi phase chỉ phụ thuộc vào contract đã freeze, không phụ thuộc code của Khoa. Rủi ro duy nhất nằm ở Phase 0, nên nó đi trước tất cả.
