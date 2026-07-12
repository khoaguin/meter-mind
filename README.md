# 🔌 MeterMind

**Voice AI Monitoring Assistant for a Fleet of Meter-Reading Chips.**

A landlord with meters scattered across many units spends hours every month walking around, photographing dials, typing numbers into a spreadsheet, computing bills, and chasing late payers. MeterMind is the software that does all of that automatically — starting from the cheapest possible sensor and ending at a voice box the owner can *ask* (in Vietnamese or English) *"who hasn't paid?"*.


---

## The big picture

The base sensor **senses** — it reads one meter and shouts a number over WiFi. It doesn't **reason** or **act**. MeterMind adds everything above the sensor: a hub to collect readings, a deterministic core to do the billing math, an AI copilot to answer questions and handle exceptions, and an owner-facing UI. Data flows *up* — from the physical meter to the human.

![MeterMind system architecture — physical meters up through edge readers, broker, hub, core, agent, to the owner UI](assets/diagrams/vision.png)


---

## The edge producer & the wire contract

How one reading is produced (the edgesim tick pipeline), the physical-device ↔ code map, the byte-exact jomjol MQTT contract, and the demo scenarios now live in **[`docs/arch.md`](docs/arch.md#the-edge-producer-in-detail--edgesim--the-wire-contract)** — moved out to keep this README focused on the high-level picture.

---

## Project layout

```
meter-mind/
├── src/edgesim/
│   ├── contract.py    # Reading + Topics — THE jomjol MQTT contract (the seam)
│   ├── reader.py      # DigitReader → DigitPrediction (jomjol's real TFLite CNN)
│   ├── assemble.py    # assemble() → MeterReadResult (digits → value/error/confidence)
│   ├── imagery.py     # CropBank, render_strip, split_strip (composite a meter face)
│   ├── device.py      # VirtualDevice — state → image → read → payload
│   ├── scenarios.py   # make_scenario → Tick (normal/leak/flatline/lowconf)
│   ├── publisher.py   # Publisher — paho-mqtt wrapper (flat + /json + status)
│   ├── fleet.py       # run_fleet — asyncio scheduler over N devices + YAML config
│   └── cli.py         # `edgesim run --config fleet.yaml`
├── src/hub/                # the ops layer above the sensor
│   ├── core/
│   │   ├── contract.py     # FROZEN Core contract — the 5 tools' return models
│   │   ├── service.py      # deterministic Core: usage, invoicing, spike detection (no model)
│   │   └── seed.yaml        # demo dataset (leak on kiosk 3, unpaid tenants)
│   ├── db/                 # SQLModel tables + idempotent seed loader (SQLite)
│   ├── api.py              # FastAPI REST — reads for the dashboard + a recapture POST
│   ├── mcp_server.py       # FastMCP streamable-http /mcp — the tools Agora calls
│   └── utility_info.py     # ask_utility_info backend → Vertex AI Agent Engine (12s cap, cache, fallbacks)
├── vn_utility_agent/         # Google ADK agent — general VN utility Q&A (Google Search grounding)
├── deploy/cloudrun-env.yaml  # Cloud Run env vars (agent resource name + canned demo answers)
├── scripts/fetch_assets.py   # download jomjol model + digit crops into data/
├── tests/                    # pytest — one file per module + a contract test
├── data/                     # (fetched) dig-class11 model + labeled digit crops
├── fleet.example.yaml        # example fleet: 3 kiosks (normal/leak/lowconf)
├── docker-compose.yml        # mosquitto broker
└── justfile                  # task runner
```

Every object that crosses a module boundary is a **Pydantic v2** model — `Reading`, `DigitPrediction`, `MeterReadResult`, `Tick`, `DeviceConfig`, `FleetConfig`, and friends — so the data shapes are validated at every seam.

---

## Quickstart

Prerequisites: [`uv`](https://docs.astral.sh/uv/), [`just`](https://github.com/casey/just), and Docker (for the broker).

```bash
just init            # uv sync + install pre-commit hooks
just fetch-assets    # download jomjol's TFLite model + digit crops into data/
just broker-up       # start the mosquitto MQTT broker (docker-compose)

# run the virtual fleet against the broker
uv run edgesim run --config fleet.example.yaml
# ...or bounded, for a quick check:
uv run edgesim run --config fleet.example.yaml --max-ticks 20
```

Watch the readings on the wire in another terminal:

```bash
mosquitto_sub -t '#' -v      # every topic from every device
```

Other tasks:

```bash
just test            # run the test suite
just check           # everything CI runs: lint + types + tests
just broker-down     # stop the broker
```

### Configuring the fleet

`fleet.example.yaml` describes the broker and one entry per device:

```yaml
broker_host: localhost
broker_port: 1883
interval_seconds: 3.0
model_path: data/models/dig-class11_1701_s2.tflite
digits_dir: data/digits
devices:
  - device_id: kiosk1
    main_topic: kiosk1-water     # becomes the MQTT MainTopic
    meter_type: water
    n_digits: 5
    decimals: 3
    start_value: 10.0
    scenario: normal             # normal | leak | flatline | lowconf
  # ...more devices
```

Adding a device is one YAML block. A real ESP32-CAM joins the same fleet by setting its `MainTopic` in the jomjol web UI to match your naming convention — no code change.

---

## Testing & CI

Tests live in `tests/`, one file per module, and **call the production code paths directly** (no shims). CI runs three secret-free jobs:

- **contract** — lint (`ruff`) + type-check (`pyrefly`) + the jomjol JSON/topic contract test. Needs no downloaded assets, runs in seconds.
- **unit** — fetches the TFLite model + digit crops (cached), then runs the full suite. Reader tests skip gracefully if the fetch is flaky, so the job stays green either way.
- **e2e** — spins up the docker-compose mosquitto broker and runs the MQTT integration test (`test_integration_mqtt.py`, marked `@pytest.mark.integration`) **over the wire**: a real subscriber on a real broker receives a device's readings and asserts the byte-exact `/json` key order, the 5 flat fields (no flat `/pre`), and the additive `confidence`/`MeterType` topics. This is the test that actually **proves the seam** — the exact bytes a downstream hub (or a flashed ESP32-CAM) will see.

Run the E2E test locally with the broker up: `uv run pytest -m integration`.

---

## The ops layer above the sensor

The simulator is the producer side. The differentiator — the agentic ops layer — is largely built.

**Built (on `main`):**

- **Hub Core** — tariff math, invoicing, payment status, threshold anomaly detection. *Code, not a model* — anything a `match`/`if` can answer.
- **SQLite store** — readings · tenants · tariffs · payments · devices, seeded to drive the demo.
- **REST API + MCP server** — the five demo tools (`query_readings`, `explain_anomaly`, `list_unpaid`, `compute_invoice`, `request_recapture`), served over Streamable HTTP and **deployed to Cloud Run**.
- **Agora cloud agent** — My Bot ConvoAI wired to the MCP endpoint; it already answers the demo questions over the five tools (verified in the voice studio).
- **Owner dashboard** — a live, read-only page served at `/` on the **same Cloud Run service** as `/mcp` (the judge-clickable **Demo URL**): fleet cards, the kiosk-3 usage spike, billing (270k / 1.86M), a recapture button, and the embedded demo video. Reads the same baked DB as the bot, so it can't drift from the voice answers.

> **Where's the brain? Not in the hub.** The signed-off architecture is **Agora-only, zero Claude in the hub** ([`docs/arch.md`](docs/arch.md)). Agora's My Bot LLM does all the routing and phrasing over MCP; every Core tool — including `explain_anomaly` — is **deterministic code** (the detector computes the spike factor; the tool returns a fixed sentence around it). The MCP endpoint is the second seam: Track B just points the voice box at one URL, nothing is flashed to the device.

**Next:**

- **Live ingest** — edgesim → hub DB over MQTT (stretch; the demo runs off seed data + Core, not the live pipe).
- **Hardware** — flash a real ESP32-CAM and point it at the same broker.

---

## VN utility info — the `ask_utility_info` tool

The one non-deterministic tool in the hub: general Vietnam electricity/water questions ("what's the current EVN tariff?", "any water outages in Ho Chi Minh City?") answered by a **Google ADK agent on Vertex AI Agent Engine**, grounded in Google Search, in voice-friendly English (the device TTS is English-only). Tenant-specific questions stay with the five deterministic tools.

```
voice device ──▶ Agora ConvoAI (My Bot LLM) ──▶ MCP on Cloud Run (/mcp)
                                                     │  ask_utility_info
                                                     ▼
                                     Vertex AI Agent Engine (vn_utility_agent,
                                     gemini-2.5-flash + google_search grounding)
```

**Pieces:**

- [`vn_utility_agent/`](vn_utility_agent/) — the ADK agent (instruction = scope, grounding, English-only, ≤3 spoken sentences). Try it locally: `just agent-run` (needs `gcloud auth application-default login`).
- [`src/hub/utility_info.py`](src/hub/utility_info.py) — the MCP-side client: ADC-only REST call to Agent Engine, **12 s hard cap**, 1 h in-memory cache keyed on the diacritics-folded question, ≤350-char sentence-boundary truncation, and a speakable apology on any failure — the voice bot never dead-airs.
- Deployed engine: `projects/161661253262/locations/asia-southeast1/reasoningEngines/507930391567400960` (`just agent-deploy` updates it in place; `just agent-deploy-new` creates a fresh one).

**Env vars on the Cloud Run service:**

| Var | What |
|---|---|
| `UTILITY_AGENT_RESOURCE_NAME` | Agent Engine resource name. Unset ⇒ the tool answers "not configured" instead of crashing. |
| `UTILITY_CANNED_ANSWERS_JSON` | Optional JSON map `{question: answer}` (values may also be `{"answer": …, "as_of": …}`) used **only when the live call fails**. Keys match after diacritics-folding, so `"gia dien hien tai la bao nhieu"` catches the accented question. |

**IAM** — the Cloud Run runtime service account must be able to query Agent Engine:

```bash
gcloud projects add-iam-policy-binding ai-playground-458112 \
  --member="serviceAccount:161661253262-compute@developer.gserviceaccount.com" \
  --role="roles/aiplatform.user" --condition=None
```

**Updating the canned demo answers** — get fresh live answers (`just agent-test` prints them, or ask the dashboard bot), then re-set the env var:

```bash
gcloud run services update meter-mind-mcp --region asia-southeast1 \
  --env-vars-file deploy/cloudrun-env.yaml
```

Verification: `just agent-test` runs the three golden demo questions (VN + EN) against the live engine; `uv run pytest tests/test_utility_info.py` covers the timeout/fallback/cache paths offline.

---

## Credits

Built on [**jomjol/AI-on-the-edge-device**](https://github.com/jomjol/AI-on-the-edge-device) (the ESP32-CAM firmware + `dig-class11` model) and its [digit dataset](https://github.com/jomjol/neural-network-digital-counter-readout)
at the [Agentic AI Build Week Hackathon - GenAI Fund (July, 2026)](https://aabw.genaifund.ai/)