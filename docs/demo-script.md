# Demo script — video với voice box (bot "2 Thằng Khờ")

> Đã verify trực tiếp trên MCP prod ngày 2026-07-11: đủ 6 tools, seed 7 phòng, `ask_utility_info` trả lời grounded trong ~5.5s.
> Nói **tiếng Anh**, chậm, rõ. Nhấn BOOT 1 lần để bắt đầu phiên, nhấn lần nữa để kết thúc.

## Checklist trước khi quay

- [ ] Thiết bị sạc đủ pin, WiFi **2.4GHz** (hotspot điện thoại bật chế độ 2.4G)
- [ ] Mở dashboard `https://meter-mind-mcp-161661253262.asia-southeast1.run.app/` trên laptop làm backup + cảnh quay
- [ ] **Warm cache**: hỏi trước 2 câu utility (điện + nước) một lần ngoài camera — cache TTL 1h → lúc quay trả lời tức thì
- [ ] Verify lại nội dung 2 câu utility ngay trước khi quay (lịch cúp nước SAWACO thay đổi theo ngày!)
- [ ] Set env `UTILITY_CANNED_ANSWERS_JSON` trên Cloud Run làm lưới an toàn cuối

## Kịch bản 8 beat (thứ tự kể chuyện)

| # | Câu hỏi (nói đúng vậy) | Tool | Đáp án kỳ vọng |
|---|---|---|---|
| 1 | *"Hello, what can you help me with?"* | — (persona) | Giới thiệu: meters, bills, who hasn't paid |
| 2 | *"How much water did kiosk one use this month?"* | `query_readings` | ~**12 cubic meters** trong July 2026 |
| 3 | *"Who has not paid yet?"* | `list_unpaid` | **4 tenants**: Bob (Room 2), Charlie (Room 3), Frank (Room 6), Grace (Room 7) |
| 4 | *"What is the bill for room two?"* | `compute_invoice` | 18 m³ × 15,000 = **270,000 VND** (Bob) |
| 5 | *"Why is kiosk three so high this month?"* | `explain_anomaly` | **Spike ~4×** ngày **July 14** — nghi rò rỉ / thiết bị lỗi |
| 6 | *"Please take a new reading of kiosk three."* | `request_recapture` | "Recapture queued for kiosk three" — beat **sense→act** |
| 7 | *"By the way, what is the current electricity price in Vietnam?"* | `ask_utility_info` | ~**2,204 VND/kWh** avg retail, "as of July 2026", nguồn EVN/MoIT |
| 8 | *"Any water outages coming up in Ho Chi Minh City?"* | `ask_utility_info` | Lịch SAWACO thật (lúc verify: cúp nước **Tan Son Hoa ward đêm 14–15/07**) |

Điểm nhấn kịch bản: beat 5 → 6 là vòng **sense → reason → act** (thấy bất thường → ra lệnh đo lại). Beat 7–8 chuyển từ "dữ liệu của tôi" sang "kiến thức thế giới thực" — cùng một chiếc box.

## Câu dự phòng (nếu ASR nghe sai)

- Beat 2: *"Show me the water usage of kiosk number one."*
- Beat 3: *"Which tenants still owe me money?"*
- Beat 5: *"Explain the anomaly on kiosk three."*
- Beat 7: *"How much does electricity cost in Vietnam right now?"*

## Lưu ý kỹ thuật khi quay

- Nói **"kiosk one/two/three"**, **"room two"** — system prompt đã map sang `kiosk1-water`, `room2`... Không cần đọc id kỹ thuật.
- Beat 7–8 lần đầu mất ~5–6s (agent + search) — đã warm cache thì tức thì; nếu quay live thì cứ để bot ngậm 5s, filler words sẽ che.
- Nếu voice chết trên set: dashboard hiển thị đủ beat 2–5 (backup demo-safe).
- Quay xen kẽ: mặt thiết bị (màn hình + LED) khi nói, dashboard khi bot đọc số — người xem đối chiếu được số liệu.

## Số liệu seed để đối chiếu nhanh (period 2026-07)

- Tariff: nước 15,000 VND/m³ · điện 3,000 VND/kWh
- room1 Alex kiosk1-water 12m³ ✅paid · room2 Bob kiosk2-water 18m³ ❌ · room3 Charlie kiosk3-elec 620kWh ❌ · room4 Dave kiosk4-elec 180kWh ✅ · room5 Eve kiosk5-water 9m³ ✅ · room6 Frank kiosk6-elec 240kWh ❌ · room7 Grace kiosk7-water 22m³ ❌
- Tổng nợ: Bob 270k + Charlie 1,860k + Frank 720k + Grace 330k = **3,180,000 VND**
- Anomaly duy nhất: kiosk3-elec, spike 4×, 2026-07-14
