# PROGRESS.md — shared task board

**How to use this file (both agents):** Read it before starting. Work tasks top to bottom. Before starting a task, change its `[ ]` to `[~] IN PROGRESS (your-name)` and commit that line first (this is the lock). When done: code + tests passing + committed, then change to `[x] DONE` and add any note under "Decisions / Notes". Only one `[~]` at a time. Pick the next free task if the top one is locked.

**Status legend:** `[ ]` todo · `[~]` in progress (locked) · `[x]` done

---

## Tier 1 — Minimum Live Product (must ship + deploy)

### Phase 0 — Scaffold
- [x] **0.1 Repo scaffold.** DONE Create the full directory structure from AGENTS.md §4, `requirements.txt`, `.env.example`, `.gitignore`, empty `__init__.py` files, and a starter `README.md`. *DoD:* `pip install -r requirements.txt` succeeds in a fresh venv; repo matches §4.
- [x] **0.2 Config + LLM wrapper.** DONE `config.py` (env settings, `MOCK_LLM`, model tiers). `llm.py` with `complete(tier, messages)` and `embed(texts)`; when `MOCK_LLM=true` return deterministic stubs (no network). *DoD:* importing core with no key works; a unit test calls `complete`/`embed` in mock mode.
- [x] **0.3 Schemas.** DONE `schemas.py` with pydantic models: `Source`, `QueryRequest`, `Citation`, `TrustReceipt` (fields per System Design §6.11), `AssuranceReport`. *DoD:* models validate; `TrustReceipt` round-trips to/from JSON.
- [x] **0.4 FastAPI skeleton.** DONE `api/main.py` with `/health` and stub `/v1/query`. *DoD:* `uvicorn api.main:app` serves; `/docs` renders; `/health` returns ok.

### Phase 1 — Synthetic data + ingestion
- [x] **1.1 Seed data.** DONE `data/seed.py` generates a synthetic, regulated-style corpus deterministically: formulary + policies (Markdown/text) with `authority_level`, `effective_date`, `supersedes` metadata; **deliberately include** (a) a versioned conflict, (b) a superseded-but-present doc, (c) a coverage gap (answerable-looking question with no source), (d) synthetic member profiles with fake PII/PHI; plus `data/synthetic/records.sqlite` for tool calls. *DoD:* running it writes files under `data/synthetic/`; re-running reproduces identical output.
- [x] **1.2 Parsers.** DONE `ingest/parsers.py` for PDF, Markdown, plain text → normalized text + metadata. *DoD:* each format parses to text with metadata in a test.
- [x] **1.3 Chunker.** DONE `ingest/chunker.py`: structure-aware (headings/sections/clauses), hierarchical (leaf→parent), deterministic, carries all governance metadata. *DoD:* test asserts chunks split on structure, are stable across runs, and retain metadata.

### Phase 2 — Index + retrieval
- [x] **2.1 Embeddings + store.** DONE `index/embeddings.py` (uses `llm.embed`) + `index/store.py` (Chroma; **mandatory `tenant_id` filter** on every query). *DoD:* ingest sample chunks; a tenant-filtered query returns only that tenant's chunks (test with two tenants).
- [x] **2.2 Query rewrite.** DONE `retrieval/rewrite.py` (nano tier). *DoD:* rewrites a messy query; passes through cleanly in mock mode.
- [x] **2.3 Retrieve + re-rank.** DONE `retrieval/retrieve.py` (wide top-20, tenant-filtered) + `retrieval/rerank.py` (local cross-encoder → top-4). *DoD:* test shows re-rank reorders candidates; returns top-k with scores.

### Phase 3 — Responder
- [x] **3.1 Evidence evaluation.** DONE `responder/evidence.py`: sufficiency check → if weak, signal abstention. *DoD:* sufficient evidence → proceed; weak → abstain signal (test both).
- [x] **3.2 Generation.** DONE `responder/generate.py` (mini tier): grounded answer + citations from top-k only. *DoD:* answer cites provided chunks; mock mode returns a deterministic grounded stub.
- [x] **3.3 Responder agent.** DONE `responder/agent.py`: intent routing (knowledge vs action; action stubbed for now) + orchestrates rewrite→retrieve→rerank→evidence→generate-or-abstain. *DoD:* end-to-end `answer(query, tenant)` returns answer or calibrated abstention.

### Phase 4 — Safety
- [x] **4.1 Redaction firewall.** DONE `safety/redaction.py`: detect PII/PHI (regex first layer) → typed placeholders before any model call → restore at edge. *DoD:* a query with a fake member id never passes raw value to `llm.complete` (assert on the mock call); output restores it.
- [x] **4.2 Input guardrails.** DONE `safety/guardrails.py`: injection pattern block + topic/scope classifier (nano). *DoD:* injection and off-scope inputs are blocked with reasons.
- [~] **4.3 Output gate.** IN PROGRESS (claude-code) `safety/output_gate.py`: groundedness gate (mini judge, binary) + domain-refusal (e.g. individualized clinical advice → refuse + escalate). *DoD:* unsupported draft is blocked; out-of-bounds request refused.

### Phase 5 — Receipt, audit, metering; wire the API
- [ ] **5.1 Audit + metering.** `audit.py` (SQLite): persist Trust Receipts, fetch by id; record tokens/latency/cost. *DoD:* a query writes a receipt; `get_receipt(id)` returns it.
- [ ] **5.2 Wire `/v1/query` + `/v1/sources` + `/v1/receipts/{id}` + `/v1/usage`.** Full path through guardrails→responder→gate→receipt. *DoD:* `/v1/query` returns a complete Trust Receipt; usage aggregates.

### Phase 6 — Console + DEPLOY (do not skip; deploy as soon as this passes)
- [ ] **6.1 Streamlit console.** `console/app.py`: chat input → answer + **evidence panel** (citations, confidence, redaction, cost/latency). Imports core directly. *DoD:* local console answers a question with evidence panel.
- [ ] **6.2 DEPLOY.** Push to GitHub; deploy console to Streamlit Community Cloud; set secrets. *DoD:* **public URL is live and answers a question.** Put the URL in README. ← MLP COMPLETE

---

## Tier 2 — Signature (Assurance Engine) — target after MLP is live

- [ ] **7.1 Attack synthesis.** `assurance/attacks.py`: generate domain-specific cases from the KB across classes — injection, PII-extraction, out-of-scope/advice, unanswerable (abstention), contradiction traps from the seeded conflict. *DoD:* returns a labeled attack set for a tenant.
- [ ] **7.2 Runner + score.** `assurance/runner.py` runs attacks through `/query`; `assurance/score.py` computes per-class results + composite Trust Score (0–100) + findings. *DoD:* `/v1/assure` returns a Trust Score + report.
- [ ] **7.3 Assurance dashboard.** Add a console tab: "Run Assurance Scan" → live green/red results + Trust Score. *DoD:* button runs scan and renders score + findings. Redeploy.

## Tier 3 — Enhancements (only if time remains)

- [ ] **8.1 Conflict resolution.** Extend `responder/evidence.py`: detect conflicting top-k, resolve by authority/recency, disclose in answer + receipt. *DoD:* the seeded conflict resolves to the current doc and discloses the superseded one.
- [ ] **8.2 MCP tool server + verified action.** `tools/mcp_server.py` + `tools/actions.py`: one read tool + one state-changing tool behind a verify-then-execute gate; agent routes action intents to it. *DoD:* an action query executes a verified, logged tool call.
- [ ] **8.3 Short-term memory.** `memory.py` + `/v1/chat`. *DoD:* follow-up question uses prior turn.
- [ ] **8.4 Semantic cache.** `cache.py`: similar repeat query short-circuits. *DoD:* a repeat query is served from cache with lower latency.
- [ ] **8.5 Evals harness + golden set.** `evals/golden.jsonl` (~30–50 cases) + a runner reporting the metrics in the eval doc. *DoD:* `python -m evals` prints metrics; the Assurance Engine reuses this scoring.

---

## Decisions / Notes
*(Agents: append one line per non-obvious choice or deviation, newest last.)*
- 0.1: Dropped `presidio-analyzer`, `presidio-anonymizer`, `spacy` from requirements — `blis` wheel fails to build on this platform (Python 3.9/macOS). PII redaction uses regex-only approach (AGENTS.md already specifies "regex first layer"). Note in safety/redaction.py task 4.1.

## Backlog (out of scope unless promoted)
*(New ideas land here, not in the build.)*
