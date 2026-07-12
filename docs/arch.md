# Architecture — Agentic Edge Meter Fleet

- Source: [`idea.md`](./idea.md).
- Diagrams [`arch.drawio`](./diagrams/arch.drawio)

![Architecture](./diagrams/arch.drawio.png)

---

## The layers (bottom → top)

Readings flow **up**; the agent's answers flow **down**. Data enters at the bottom, the owner asks at the top.

| Layer | What it is | Status |
|---|---|---|
| **Simulated Edge Fleet** | `edgesim` — 3 ESP32-CAM devices, each runs the **real jomjol TFLite CNN** on digit crops, publishes over MQTT. Scenarios: `kiosk1-water` normal, `kiosk2-water` leak, `kiosk3-elec` low-confidence. | **BUILT** |
| **MQTT Broker** | `mosquitto` — a pub/sub **pipe**. Transports readings; stores nothing. No subscriber = the message is gone. | BUILT (compose) |
| **Hub — FastAPI backend** | **Core** (deterministic code), **SQLite** (one file), **REST API**, **MCP server** (exposes the Core tools to Agora). No model runs in the hub. **Deployed to Cloud Run** (`meter-mind-mcp`); MQTT→DB ingest is a stretch. | **BUILT** |
| **Owner Dashboard** | Read-only page: devices · latest reads · paid/unpaid · usage chart · the demo video. Served at `/` on the **same Cloud Run service** as `/mcp` — the public **Demo URL**. Backup + visual while the box talks. | **BUILT** |
| **Voice Box** | Agora My Bot (ASR·LLM·TTS) + ESP32-S3. **Cloud agent BUILT** — My Bot answers over the deployed MCP tools. The physical ESP32-S3 flash/pair is the remaining piece (Build Day). | **cloud agent BUILT · HW next** |

### Two storages — don't conflate them

| | Chip SD card | Hub SQLite DB |
|---|---|---|
| Holds | model, config, web files, image/log scratch | readings · tenants · tariffs · payments · devices |
| Scope | one device, local | whole fleet, central |
| Queryable | no | yes — every demo answer comes from here |
| In the sim | collapses to `data/models/` + `data/digits/` | the real build |

The chip is **stateless**: snap → read → publish. It keeps only `pre` (last value, to compute rate). There is **no per-chip database**.

---

## The seam: the Core API

`Core` is a pure-code module (tariff math, invoicing, payment status, anomaly flags). It is the **one contract** the whole system hangs on:

- The **Dashboard** reads it over REST (read-only).
- The **Voice Box** (Agora My Bot — ASR·LLM·TTS) reaches the tools through an **MCP server** (thin wrapper over Core). Agora's own LLM does all the routing and phrasing; every tool — including `explain_anomaly` — is **deterministic code, no model inside the hub** (the anomaly detector computes the factor; the tool returns a fixed English sentence around it). Agora natively supports MCP (Feb 2026): we set **one URL** in the cloud agent config (`llm.mcp_servers`, `transport_type: "http"` = Streamable HTTP) — nothing is flashed to the device, no custom glue.

**Deployed — one service, two doors.** The hub image (Core + seeded SQLite + REST + MCP) runs on **Cloud Run**; CD builds and deploys it on merge to `main`. A single service hosts both: **`/mcp`** for Agora's bot (streamable-HTTP, the machine endpoint) and **`/`** for the owner dashboard (live, same-origin, no CORS — the judge-clickable **Demo URL**). Both read the same baked DB, so the dashboard can never drift from the voice answers. Live: `https://meter-mind-mcp-fkoupnt5ua-as.a.run.app/` (dashboard) · `…/mcp` (bot). The dashboard routes are plain HTTP added to the MCP server's app (`hub/web.py`); they are **not** MCP tools, so Agora neither sees nor needs them.

---

## The real gap

`edgesim` only produces **readings**. The demo needs **tenants, tariffs, bills, payments, an anomaly** — none exist yet. That gap *is* the build: a data model + Core + agent + **seed data**.

The 5 demo answers need **Core + good data, not the live pipe**. So the P0 spine is seed-DB + Core + agent; live MQTT ingest is a bonus that makes it feel live.

---

## From seed to answer — how a demo number is computed

Every demo answer is **deterministic code over seeded data** — no model ever touches a number. The chain:

1. **`seed.yaml` holds the truth** ([`src/hub/core/seed.yaml`](../src/hub/core/seed.yaml)) — tenants, tariffs (`water: 15000`, `elec: 3000` VND per m³ / kWh), each account's `usage` total and `paid` flag, and the one anomaly (`kiosk3-elec`, 4× spike on `2026-07-14`).
2. **The DB seed loader expands it** — each `usage` total is spread into a **cumulative per-day reading series** (`hub.db.seed_loader`), so the DB looks like a real month of meter reads, not a single number. The series reconciles back exactly: `Σ(daily deltas) == last_face − opening == usage`.
3. **Core derives on read** (`hub.core.service` — opens its own `Session`, no model, no shared state):
   - `usage = last_reading − PERIOD_OPENING_FACE(0.0)`
   - `amount = usage × tariff_rate`
   - `unpaid` = accounts with `paid: false`
   - spike `factor = max_day / median(baseline_days)`, flagged past threshold `3.0`
4. **A tool returns it** — the MCP tool / REST route wraps the number in a fixed Pydantic model. Agora's My Bot only *phrases* it (VN/EN); the value is already final.

**Worked — the 5 demo beats:**

| Beat (owner asks) | Tool | Number | Where it comes from |
|---|---|---|---|
| "kiosk 3 this month?" | `query_readings` | 620 kWh | seed `usage` → per-day series sum |
| "why so high?" | `explain_anomaly` | ~4× on 14/07 | `factor = max_day / median(baseline)` |
| "who hasn't paid?" | `list_unpaid` | Room 2 · Room 3 | `paid: false` in seed |
| "Room 2's bill?" | `compute_invoice` | **270,000 VND** | 18 m³ × 15000 |
| "Room 3's bill?" | `compute_invoice` | **1,860,000 VND** | 620 kWh × 3000 |

Change a number in `seed.yaml`, re-seed, and every answer moves with it. That's the point: **the data is the script, the Core is the calculator, the LLM is just the voice.**

---

## The edge producer in detail — edgesim & the wire contract

> Moved out of the README to keep it focused: how the simulated fleet turns usage into a byte-exact jomjol reading, the physical-device ↔ code map, the MQTT contract, and the demo scenarios.

### How one reading is produced

Every interval, each virtual device runs the same chain a flashed ESP32-CAM runs on-chip. `VirtualDevice.step()` in `device.py` orchestrates it:

![The edgesim tick pipeline — usage tick, advance value, paint meter face from real crops, run the TFLite CNN, assemble the number, wrap in the jomjol payload, publish to MQTT](../assets/diagrams/pipeline.png)

1. **Usage tick** — the device's `Scenario` picks this interval's change (`scenarios.py`).
2. **Advance the meter** — the running value moves by that delta and becomes a zero-padded digit string.
3. **Paint the meter face** — real digit crops are composited into a strip image; if the reading is mid-roll, a `NaN` crop is injected (`imagery.py`).
4. **Read the digits** — jomjol's real CNN classifies each digit and returns a softmax confidence (`reader.py`).
5. **Assemble the number** — digits become one validated reading; an uncertain digit flags an error and holds the last good value (`assemble.py`).
6. **Wrap in the jomjol payload** — the reading is packaged as the exact wire format (`contract.py`).
7. **Publish to MQTT** — flat per-field topics, the `/json` body, plus our additive topics, go to the broker (`publisher.py`).

### Connecting the concepts: physical device ⟷ code

If you know how the ESP32-CAM works but not the code (or vice-versa), this is the map. Each thing a real chip does on a meter corresponds to a specific edgesim class.

![Rosetta stone mapping each physical action of an ESP32-CAM to the edgesim class and file that simulates it](../assets/diagrams/mapping.png)

| A real ESP32-CAM… | …is simulated by | in |
|---|---|---|
| The number on the meter face (current + last accepted) | `DeviceState.value` / `.pre_value` | `device.py` |
| One meter-reader device (id, type, digits, decimals) | `VirtualDevice` + `DeviceConfig` | `device.py` |
| How usage moves the number (steady / leak / dead / flaky) | `make_scenario(kind, seed)` → `Tick{delta, rolling}` | `scenarios.py` |
| Camera photographs the digit roller / LCD | `CropBank` · `render_strip` · `split_strip` | `imagery.py` |
| On-chip neural net recognizes each digit | `DigitReader.predict_crop` → `DigitPrediction` | `reader.py` |
| Firmware assembles digits into one reading | `assemble()` → `MeterReadResult` | `assemble.py` |
| The MQTT payload it publishes | `Reading` + `Topics` ◀ **the seam** | `contract.py` |
| WiFi radio pushes to the broker | `Publisher.publish_reading` | `publisher.py` |
| Many chips on a timer reporting to a hub | `run_fleet` + `FleetConfig` | `fleet.py` |

### The jomjol MQTT contract (the producer seam)

Both the simulator and a real chip publish under a per-device **`MainTopic`** (e.g. `kiosk1-water`), with a message **`group`** that defaults to `main`. The consumer treats both producers identically.

![The MQTT contract — two producers publishing byte-identical topics under one MainTopic, fanning out to flat fields, the /json payload, additive topics, and device status](../assets/diagrams/contract.png)

**Topics published for one device** (`MainTopic` = `kiosk1-water`):

| Topic | Kind | Notes |
|---|---|---|
| `kiosk1-water/main/value` `…/raw` `…/error` `…/rate` `…/timestamp` | Native jomjol — flat (5) | one topic per field. **There is no flat `/pre`** — `pre` lives only in `/json`. |
| `kiosk1-water/main/json` | Native jomjol — the source of truth | the full 6-field payload (below). |
| `kiosk1-water/main/confidence` | **Additive (ours)** | CNN softmax confidence, 4-decimal string. A real chip omits this. |
| `kiosk1-water/MeterType` | **Additive (ours)** | `water` / `electricity`. A real chip omits this. |
| `kiosk1-water/Hostname` `/IP` `/MAC` `/Uptime` `/wifiRSSI` | Native jomjol — status | device health. |

**The `/json` body** — byte-exact jomjol, fixed key order, every value a string:

```json
{"value":"11.234","raw":"11.234","pre":"10.000","error":"no error","rate":"1.234000","timestamp":"2026-06-27T10:00:00"}
```

- `value` — the validated reading (the number to trust). `raw` — the uncorrected OCR result. `pre` — the previous accepted value (basis for `rate`).
- `error` is the literal string `"no error"` when clean, otherwise the rejection reason. Treat it as **free text**; only `"no error"` means clean.
- `rate` is emitted as a **string** here (jomjol's firmware does the same), though jomjol's docs show it as a number — a consumer must tolerate both.

The tolerance rules that let a real chip and the simulator share one broker (local planning notes): additive topics are optional, unknown topics are ignored, `error` is free text, and values are compared with tolerance — not byte-for-byte.

### The demo scenarios

Each device is driven by a scripted usage profile (`scenarios.py`) so a demo shows the interesting cases, not just steady counting:

| Scenario | Behaviour | Demonstrates |
|---|---|---|
| `normal` | small random increments; ~10% mid-roll frames | a healthy meter |
| `leak` | normal for a few ticks, then a large sustained spike | anomaly / leak detection |
| `flatline` | value never changes | a broken or stuck meter |
| `lowconf` | ~70% mid-roll frames → frequent `NaN` reads | the **low-confidence escalation loop** the agent will handle |
