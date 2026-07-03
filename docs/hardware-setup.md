# Hardware Setup Log — ESP32-CAM (AI-on-the-edge-device)

Status as of 2026-07-03. Chip flashed and verified; waiting on microSD card (arrives ~2026-07-05).

## Device

| | |
|---|---|
| Board | ESP32-CAM (AI-Thinker style) |
| Chip | ESP32-D0WD-V3, revision v3.1, 40MHz crystal |
| MAC | `d4:e9:f4:a7:71:3c` |
| USB | USB-serial adapter with CH340 chip (vendor `0x1A86`, product `0x7523`), adapted to USB-C |
| Serial port on macOS | `/dev/cu.usbserial-210` (number can change on replug) |
| Firmware | jomjol AI-on-the-edge-device **v16.1.0** (flashed + hash-verified 2026-07-03) |

## Connecting on macOS

1. Plug in. Find the port:
   ```bash
   ls /dev/cu.usb*
   ```
2. CH340 driver is built into macOS 11+ — no install needed. Device shows as `USB Serial` in `ioreg -p IOUSB -l -w0`.
3. Test the connection:
   ```bash
   uvx --from esptool esptool --port /dev/cu.usbserial-210 chip-id
   ```
4. Serial monitor for debugging:
   ```bash
   screen /dev/cu.usbserial-210 115200   # quit: ctrl-a k
   ```

## Problems hit + fixes

### 1. Web installer: "Failed to open serial port"

Chrome at jomjol.github.io failed with `Failed to execute 'open' on 'SerialPort'`. `lsof` showed nothing holding the port — not a busy-port problem.

### 2. esptool: `termios.error: (22, 'Invalid argument')`

Same root cause as #1: the CH340 port was in a bad driver state. Both Chrome and esptool failed to open it.

**Fix: unplug and replug the USB cable.** Port re-enumerates and works. This is the first thing to try on any serial-open failure with this board.

### 3. ESP32 flash too small for anything but firmware

Chip has 4MB flash. Web UI, TFLite models, config, photos, and logs all live on a **microSD card — mandatory**, not optional. No card = boot halts with SD error. The Mac cannot substitute as network storage; the chip reads the card over its local SD bus.

## Flashing procedure (done, repeat for new devices)

```bash
# 1. Download release
gh release download v16.1.0 -R jomjol/AI-on-the-edge-device \
  -p 'AI-on-the-edge-device__manual-setup__v16.1.0.zip'
unzip AI-on-the-edge-device__manual-setup__v16.1.0.zip -d manual-setup

# 2. Flash (bootloader / partition table / app)
cd manual-setup
uvx --from esptool esptool --port /dev/cu.usbserial-210 --baud 460800 --chip esp32 \
  write-flash 0x1000 bootloader.bin 0x8000 partitions.bin 0x10000 firmware.bin
```

If it hangs at "Connecting...": hold IO0/BOOT (or GPIO0→GND) during retry, release after connect. Not needed with the MB adapter board — auto-reset worked.

## microSD card

**Requirements:**
- Any size ≥ 512MB; firmware uses <1GB. 16–32GB ideal.
- **FAT32 required.** ≤32GB cards ship FAT32; >32GB ship exFAT and need reformat:
  ```bash
  diskutil eraseDisk FAT32 SDCARD MBRFormat /dev/diskN
  ```
- ESP32-CAM SD slots are picky — stick to genuine SanDisk/Lexar Class 10. No-name cards (SDATA, MAXBY, Yoosee, Hoco) are the top cause of "SD init failed".
- Speed class doesn't matter (chip writes at ~SPI speed) — don't pay for Extreme PRO/V30/A2.

**Shopee buying notes (2026-07-03):**
- Ordered: SanDisk Ultra **32GB**, 227.941đ, SanDisk Official Shop listing (3k+ sold, 371 reviews, 4.9★), delivery ~July 5.
- Search that worked: `thẻ nhớ microSD SanDisk Ultra 32GB` + Shopee Mall filter + sort Bán Chạy.
- Rejected: SDATA no-name (0 reviews, fake-capacity risk at SanDisk price), "Ultra Extreme Pro" mash-up listings (2× price for the real variant, counterfeit red flags).
- Fleet note: one card per device — buy multi-packs for the fleet build-out.

**Card contents** (extracted, ready to copy): scratchpad `manual-setup/sd-card/` — from `sd-card.zip` inside the manual-setup release zip. Contains `html/`, `config/`, `wlan.ini`, `demo/`, `firmware/`, `img_tmp/`, `log/`.

## Remaining steps (when card arrives)

1. Card into Mac. Verify/format FAT32.
2. Edit `wlan.ini`: set `ssid` and `password` (leave empty → chip opens AP `AI-on-the-edge`, config at `http://192.168.4.1`).
3. Copy contents of `sd-card/` to card root.
4. Card into chip, power on. Chip joins WiFi.
5. Web UI at `http://watermeter.local` or its DHCP IP (`arp -a` / router list).
6. In the UI: aim camera at meter, set reference + ROIs, pick digit model. Readings then flow via REST/MQTT — the input for the fleet/agent layer.
7. Enable MQTT (off by default): Settings → MQTT. URI = `mqtt://<mac-lan-ip>:1883` (get IP: `ipconfig getifaddr en0`), no user/password (broker allows anonymous), set MainTopic to the fleet convention `<device>-<type>` (e.g. `kiosk1-water`), not the default `watermeter`. Broker = the simulator's dockerized mosquitto (`docker compose up -d mosquitto`); it binds all interfaces so the chip reaches it over WiFi. Verify: `mosquitto_sub -t '#' -v` shows chip topics next to simulator topics.
