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

## Ownership & build plan (2 engineers, 3 days)

Focus: **A (spine) + Voice/Agora** — Agora is the sponsor, chips in hand. The seam splits the work cleanly; after the Day-1 freeze there is **zero shared state**.

| | **Track A — Software spine** | **Track B — Physical / voice edge**|
|---|---|---|
| Owns | DB + seed · Core · REST · Dashboard · **MCP server** | Agora ESP32-S3 flash · My Bot persona · VN-voice check · point My Bot at the MCP endpoint · tune conversation |
| Deliverable to the other | a running **MCP endpoint + tool docs** | — (consumes the endpoint) |
| Stretch | live MQTT ingest (edgesim→DB) | real jomjol meter chip |

Track B do not need to touch Python Core — just points Agora at the endpoint URL. Minimal integration surface.
