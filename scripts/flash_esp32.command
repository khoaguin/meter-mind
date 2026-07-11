#!/bin/bash
# MeterMind — Flash Agora ConvoAI firmware (zhengchen-1.54tft-wifi) lên ESP32-S3
# Theo "Agora AI Bot Setup and Firmware Flashing Guide" (docs/agora-ai-bot-setup-guide.pdf)
# Cách chạy: double-click file này trong Finder (hoặc: bash scripts/flash_esp32.command)
set -e

echo "=== MeterMind ESP32-S3 flasher ==="

# ── 1. Python venv + esptool ─────────────────────────────────────────────
VENV="$HOME/xiaozhi-venv"
if [ ! -d "$VENV" ]; then
  echo "[1/4] Tạo venv tại $VENV ..."
  python3 -m venv "$VENV"
else
  echo "[1/4] Venv đã có: $VENV"
fi
source "$VENV/bin/activate"
python -m pip install --quiet --upgrade esptool
echo "      esptool: $(esptool version 2>/dev/null | head -1 || esptool.py version | head -1)"

# ── 2. Tìm serial port của ESP32 ─────────────────────────────────────────
echo "[2/4] Tìm serial port ..."
PORT=$(ls /dev/cu.wchusbserial* /dev/cu.usbserial* /dev/cu.usbmodem* 2>/dev/null | head -1 || true)
if [ -z "$PORT" ]; then
  echo ""
  echo "❌ Không thấy /dev/cu.wchusbserial* / cu.usbserial* / cu.usbmodem*."
  echo "   💡 MẸO: rút thiết bị ra, GIỮ NÚT BOOT, cắm lại trong lúc vẫn giữ (ép vào bootloader"
  echo "      → board dùng USB native sẽ hiện /dev/cu.usbmodem*), rồi chạy lại script."
  echo "   1) Kiểm tra đã cài driver WCH CH34x chưa (CH341SER_MAC trong Downloads):"
  echo "      mở file .dmg → chạy .pkg → nhập mật khẩu → System Settings ▸ Privacy & Security ▸ Allow"
  echo "      → RESTART Mac nếu installer yêu cầu."
  echo "   2) Rút cáp cắm lại (dùng cáp DATA, không phải cáp chỉ sạc), thử cổng USB khác."
  echo "   Các port hiện có:"
  ls /dev/cu.* 2>/dev/null | sed 's/^/      /'
  exit 1
fi
echo "      Port: $PORT"

# ── 3. Tìm firmware trong ~/Downloads ────────────────────────────────────
echo "[3/4] Tìm firmware zhengchen* trong ~/Downloads ..."
FW=$(find "$HOME/Downloads" -maxdepth 2 -iname 'zhengchen*.bin' 2>/dev/null | head -1 || true)
if [ -z "$FW" ]; then
  ZIP=$(find "$HOME/Downloads" -maxdepth 1 -iname 'zhengchen*.zip' 2>/dev/null | head -1 || true)
  if [ -n "$ZIP" ]; then
    echo "      Thấy $ZIP → giải nén ..."
    unzip -o -q "$ZIP" -d "$HOME/Downloads/zhengchen-fw"
    FW=$(find "$HOME/Downloads/zhengchen-fw" -iname '*.bin' | head -1 || true)
  fi
fi
if [ -z "$FW" ]; then
  echo "❌ Không tìm thấy file .bin (zhengchen*). Tải firmware 'zhengchen-1.54tft-wifi (ESP32-S3)'"
  echo "   từ My Bot portal (⋮ → Devices → Add Device → Pair a New Device) rồi chạy lại."
  exit 1
fi
echo "      Firmware: $FW"

# ── 4. Flash ─────────────────────────────────────────────────────────────
echo ""
echo "[4/4] ⚠️  GIỮ NÚT BOOT trên thiết bị (nút giữa, cạnh volume) rồi nhấn Enter để flash..."
read -r
esptool --chip esp32s3 \
  --port "$PORT" \
  --baud 460800 \
  write-flash \
  --flash-mode dio \
  --flash-freq 80m \
  --flash-size 16MB \
  0x0 "$FW" || \
esptool.py --chip esp32s3 --port "$PORT" --baud 460800 write_flash \
  --flash_mode dio --flash_freq 80m --flash_size 16MB 0x0 "$FW"

echo ""
echo "✅ Flash xong! Các bước tiếp theo (trên thiết bị):"
echo "   1. Nhấn nút POWER để khởi động."
echo "   2. GIỮ nút BOOT → vào WiFi pairing mode."
echo "   3. Trên Mac/điện thoại: nối WiFi hotspot 'xiaozhi-38DD' → mở http://192.168.4.1/"
echo "      → nhập SSID + password WiFi nhà (2.4GHz ONLY)."
echo "   4. Thiết bị hiện + đọc pair code 6 số → nhập vào My Bot portal"
echo "      (bot '2 Thằng Khờ' → ⋮ → Devices → Add Device) → Bind device."
echo "   5. Nhấn BOOT 1 lần để bắt đầu nói chuyện. Hỏi thử: 'Who has not paid?'"
