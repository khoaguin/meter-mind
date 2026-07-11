# Prompt for coding agent — ADK "VN Utility Info" agent + MCP integration

> Paste everything below into the coding agent. Context: repo `khoaguin/meter-mind`, existing FastMCP server (`meter-mind-hub`) already deployed on Cloud Run at `https://meter-mind-mcp-161661253262.asia-southeast1.run.app/mcp`, consumed by an Agora ConvoAI voice bot (English-only TTS).

---

Build and deploy a **Google ADK (Agent Development Kit, Python) agent** that answers general questions about electricity and water utilities in Vietnam, then integrate it into our existing FastMCP server as a new tool. Work in this order and stop at each checkpoint if something fails.

## 1. The ADK agent

Create package `vn_utility_agent/` with a root `Agent` (framework: `google-adk`):

- **Model:** `gemini-2.5-flash` (favor low latency over depth).
- **Tools:** built-in `google_search` grounding tool. Every factual answer about current prices, schedules, or regulations MUST come from search results, never from model memory.
- **Instruction (system prompt)** — requirements it must encode:
  - Scope: general Vietnam utility information — EVN electricity tariffs, water prices, planned power/water outage schedules (especially Ho Chi Minh City / SAWACO, EVNHCMC), how tariff tiers work, utility regulations. Refuse (politely, one sentence) anything outside utilities.
  - **Always answer in English**, even when the question arrives in Vietnamese — the downstream voice device has English-only TTS. Translate Vietnamese place names sensibly (giữ nguyên proper nouns: "Thu Duc", "District 7").
  - Voice-friendly output: 1–3 short sentences, no markdown, no lists, no URLs, no symbols. Numbers spoken naturally ("about three thousand four hundred dong per kilowatt hour" is better than "3,461 VND/kWh" — but include the digits once for clarity).
  - Time-qualify everything: "As of <month year>, ..." and mention the source name in prose ("according to EVN", "per SAWACO's announcement").
  - If search returns nothing solid, say so honestly in one sentence — do not guess.
- Example questions it must handle well (test with these, asked in BOTH Vietnamese and English):
  1. "Giá điện hiện tại là bao nhiêu?" / "What is the current electricity price in Vietnam?"
  2. "Sắp tới có lịch cúp nước ở thành phố Hồ Chí Minh không?" / "Any upcoming water outages in Ho Chi Minh City?"
  3. "Tại sao hóa đơn điện tháng này cao hơn?" (general tariff-tier explanation, NOT tenant-specific)

**Checkpoint 1:** `adk run` (or `adk web`) locally answers all 3 questions in English, grounded, ≤3 sentences each.

## 2. Deploy to Vertex AI Agent Engine

- Project: the current GCP project (same as the Cloud Run service `meter-mind-mcp`, project number `161661253262`).
- Region: **`asia-southeast1`** to colocate with Cloud Run. If Agent Engine is not available in `asia-southeast1`, fall back to `us-central1` and note it.
- Use `adk deploy agent_engine` (needs a staging GCS bucket — create `gs://<project>-adk-staging` if missing).
- Record the resource name: `projects/<num>/locations/<region>/reasoningEngines/<id>`.

**Checkpoint 2:** calling the deployed agent from a local Python snippet (`vertexai.agent_engines.get(<resource>).stream_query(...)` or `.query(...)`) returns a grounded English answer.

## 3. Integrate into the existing FastMCP server

Add ONE new tool to the existing FastMCP server (same style as current tools):

```
ask_utility_info(question: str) -> {"answer": str, "as_of": str}
```

- Docstring/description (the ConvoAI LLM routes on this — be precise): "General Vietility information for Vietnam: current electricity/water tariffs, planned outage schedules (e.g. Ho Chi Minh City), how pricing tiers work, regulations. Use for general knowledge questions only — NOT for this landlord's tenants, invoices, meter readings, or payments (use the other tools for those)."
- Implementation: call the deployed Agent Engine using **Application Default Credentials** — the Cloud Run service account, no key files, no secrets in code. Env var `UTILITY_AGENT_RESOURCE_NAME` holds the resource name; if unset, the tool returns a clear "not configured" answer instead of crashing.
- **Timeout + fallback:** hard cap the agent call at 12 seconds. On timeout or any exception, return `{"answer": "Sorry, I could not reach the utility information service just now. Please try again in a moment.", ...}` — the voice bot must always get something speakable.
- Keep the answer under ~350 characters; truncate at a sentence boundary if longer.

IAM: grant the Cloud Run runtime service account `roles/aiplatform.user` on the project (emit the exact `gcloud` command in the README/PR description; don't assume it's done).

**Checkpoint 3:** after redeploying Cloud Run, an MCP `tools/call` of `ask_utility_info` with question "Giá điện hiện tại là bao nhiêu?" returns a grounded English answer end-to-end in <12s.

## 4. Demo safety net

- Add a tiny in-memory cache (question-normalized, TTL 1 hour) so repeating a demo question is instant.
- Add optional env `UTILITY_CANNED_ANSWERS_JSON` — a JSON map of canned fallbacks checked ONLY when the live call fails, pre-filled with current answers for the 2 demo questions (electricity price, HCMC water outage). Stage networks are hostile; the demo must never dead-air.

## 5. Deliverables

- `vn_utility_agent/` package + deploy script/instructions (`just` recipes welcome; repo uses justfile).
- MCP server diff adding `ask_utility_info`.
- README section: architecture (voice → ConvoAI cloud → MCP on Cloud Run → Agent Engine → Google Search), IAM command, env vars, how to update canned answers.
- Tests: unit test for timeout/fallback path (mock the agent call); the 3 golden questions documented in a test file even if the live test is marked manual.

## Constraints

- Python 3.12, `uv` for deps, match existing repo lint (ruff) and typing (pyrefly) conventions.
- Do not modify existing MCP tool names/schemas — the contract is frozen.
- No secrets or key files in the repo; ADC only.
- Remember the My Bot MCP timeout is 10–20s total: keep the whole tool call comfortably under it.
