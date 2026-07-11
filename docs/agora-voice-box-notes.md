# Agora Voice Box — Phase 0 findings & working notes

> Nguồn: tài liệu BTC "Agora AI Bot Setup and Firmware Flashing Guide" (`docs/agora-ai-bot-setup-guide.pdf`) + khảo sát trực tiếp My Bot portal (2026-07-09).
> Liên quan: Epic [#17](https://github.com/khoaguin/meter-mind/issues/17) · spike #25 (MCP) · spike #26 (VN voice, **closed**).
>
> **Cập nhật 2026-07-11:** MCP đã deploy lên **Cloud Run** + gắn vào bot → **cloud agent chạy được** (trả lời các câu demo qua MCP tools). **Dashboard / Demo URL** đã lên cùng service, phục vụ ở `/`. Còn lại: **flash ESP32-S3** (Build Day 12/07).

## Trạng thái hiện tại

| Hạng mục | Trạng thái |
|---|---|
| Agora project | ✅ Đã tạo — tên **Meter Mind** |
| Bot | ✅ Đã tạo & config — **"2 Thằng Khờ"**, id `agent_oIq3xvvITV13`, portal: https://mybot.sg3.agoralab.co/agents/agent_oIq3xvvITV13 |
| Language | English (persona hiểu tiếng Việt nhưng luôn trả lời EN) |
| Voice | Mabel (default BytePlus). EN thuần: Tim. Multilingual đáng thử: Jess, Vivi, Mindy |
| System prompt / persona / welcome | ✅ Đã set (MeterMind landlord copilot, câu ngắn cho TTS, đọc số tự nhiên, chỉ trả lời từ MCP tool data) |
| MCP server | ✅ **Đã gắn & chạy** — endpoint `https://meter-mind-mcp-fkoupnt5ua-as.a.run.app/mcp` (deploy qua CD lên Cloud Run). Cloud agent trả lời được các câu demo qua MCP tools (verified trong Preview). |
| Owner dashboard / **Demo URL** | ✅ **Đã build & deploy** — cùng service Cloud Run, phục vụ ở `/` (root): `https://meter-mind-mcp-fkoupnt5ua-as.a.run.app/`. Link bấm-được cho judge (không login, không mic): fleet · spike kiosk 3 · hóa đơn · video demo. |
| Flash thiết bị ESP32-S3 | ⬜ Chưa làm — để **Build Day 12/07** |

## Phát hiện quan trọng

**1. My Bot CÓ hỗ trợ custom MCP server** (đóng phần lớn #25). Form "Add MCP server":

- **Name**: ≤48 ký tự, chỉ chữ/số/`.`/`-`
- **Endpoint URL**: dạng `https://example.com/mcp` → streamable HTTP
- **Timeout (ms)**: vd 5000
- **Headers**: key/value tùy ý → dùng được cho auth token

**2. ⚠️ MCP server được gọi từ cloud ConvoAI của Agora, KHÔNG phải từ thiết bị.** ("Configure a custom MCP server passed to ConvoAI when a session starts.") Hệ quả cho #30/#14: MCP endpoint của Hub **phải public**. **✅ Đã giải quyết (2026-07-11):** endpoint public sẵn nhờ **Cloud Run** (`…/mcp`) — không cần ngrok/cloudflared nữa; URL cố định, luôn bật.

**3. Không có tiếng Việt** (#26 — closed). Language chỉ có 中文/English/日本語/한국어; voice list không có VN TTS. **Quyết định: demo bằng tiếng Anh.** Follow-up: thử voice multilingual với text tiếng Việt; hỏi mentor Agora về VN voice.

## Quy trình flash ESP32-S3 (tóm tắt từ guide, cho #35)

1. `python3 -m venv ~/xiaozhi-venv && source ~/xiaozhi-venv/bin/activate && pip install esptool`
2. macOS: cài driver WCH CH34x (github.com/WCHSoftGroup/ch34xser_macos) — chú ý cho phép trong Security settings.
3. Cắm thiết bị, tìm port: `ls /dev/cu*` → vd `/dev/cu.wchusbserial1110`
4. Portal → bot → ⋮ → Devices → Add Device → Pair a New Device → tải firmware **zhengchen-1.54tft-wifi (ESP32-S3)**
5. **Giữ nút BOOT** rồi chạy:
   ```
   esptool --chip esp32s3 --port /dev/cu.wchusbserial1110 --baud 460800 \
     write-flash --flash-mode dio --flash-freq 80m --flash-size 16MB \
     0x0 <PATH>/zhengchen_1_54tft_ml307_sg3.bin
   ```
6. Nhấn Power để khởi động → **giữ BOOT** vào chế độ pairing WiFi → nối hotspot `xiaozhi-38DD` → mở `http://192.168.4.1/` nhập WiFi (**2.4GHz only** — lưu ý #14 demo-day) → thiết bị đọc pair code 6 số → nhập vào portal → Bind device.

## Nút bấm (khi demo)

- **Power**: bật/tắt máy
- **BOOT giữ lâu**: vào WiFi config mode
- **BOOT nhấn 1 lần**: bắt đầu / kết thúc phiên nói chuyện với bot

## Việc tiếp theo (thứ tự)

1. ✅ **Xong** — Test Preview trên web với persona hiện tại ("who has not paid?", "why is kiosk 3 so high?") → cloud agent trả lời đúng qua MCP tools.
2. ✅ **Xong** — MCP endpoint deploy lên **Cloud Run** (`https://meter-mind-mcp-fkoupnt5ua-as.a.run.app/mcp`), gắn vào bot, verify tool call OK (#28/#25). Dashboard/Demo URL lên **cùng service** ở `/`.
3. ⬜ **Còn lại** — Flash + pair thiết bị ESP32-S3 (#35), Build Day 12/07.
