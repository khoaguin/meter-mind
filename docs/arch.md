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
| **Hub — FastAPI backend** | Our build. Four parts: **Ingest** (MQTT→DB), **SQLite** (one file), **Core** (deterministic code), **MCP server** (exposes the Core tools to Agora). No model runs in the hub. | **TO BUILD** |
| **Owner Dashboard** | Read-only page: devices · latest reads · paid/unpaid. Backup + visual while the box talks. | TO BUILD |
| **Voice Box** | Agora ESP32-S3 + My Bot (ASR·LLM·TTS). The owner talks; the agent speaks back. | TO BUILD (real HW) |

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

---

## The real gap

`edgesim` only produces **readings**. The demo needs **tenants, tariffs, bills, payments, an anomaly** — none exist yet. That gap *is* the build: a data model + Core + agent + **seed data**.

The 5 demo answers need **Core + good data, not the live pipe**. So the P0 spine is seed-DB + Core + agent; live MQTT ingest is a bonus that makes it feel live.

---

## Ownership & build plan (2 engineers, 3 days)

Focus: **A (spine) + Voice/Agora** — Agora is the sponsor, chips in hand. The seam splits the work cleanly; after the Day-1 freeze there is **zero shared state**.

| | **Track A — Software spine** | **Track B — Physical / voice edge**|
|---|---|---|
| Owns | DB + seed · Core · REST · Dashboard · **MCP server** | Agora ESP32-S3 flash · My Bot persona · VN-voice check · point My Bot at the MCP endpoint · tune conversation |
| Deliverable to the other | a running **MCP endpoint + tool docs** | — (consumes the endpoint) |
| Stretch | live MQTT ingest (edgesim→DB) | real jomjol meter chip |

Track B do not need to touch Python Core — just points Agora at the endpoint URL. Minimal integration surface.
