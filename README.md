# Veritrace

**Grounded, cited answers over private knowledge — with a sealed Trust Receipt on every response.**

[![Live Demo](https://img.shields.io/badge/Live%20Demo-veritrace--app.streamlit.app-1d4ed8?style=flat-square)](https://veritrace-app.streamlit.app)
[![Tests](https://img.shields.io/badge/Tests-246%20passing-059669?style=flat-square)](#)
[![Python](https://img.shields.io/badge/Python-3.9%2B-3b82f6?style=flat-square)](#)
[![License](https://img.shields.io/badge/License-MIT-64748b?style=flat-square)](#)

---

## Overview

AI deployments in regulated organizations stall because there is no continuous, auditable proof that the system is grounded, compliant, and safe. Veritrace solves this with three interlocking mechanisms:

1. **Trust Receipt** — every response is sealed with a provenance record: exact source citations, confidence band, conflict resolution log, PII redaction record, groundedness score, cost, and latency.
2. **Safety firewall** — a PII/PHI redaction layer strips sensitive identifiers before any model call and restores them at the edge. Input guardrails block injections and off-scope queries. An output gate blocks clinical advice and ungrounded claims.
3. **Autonomous Assurance Engine** — continuously attacks the deployed system across five adversarial classes, scores results, and produces a live Trust Score (0–100) — surfacing gaps before they become incidents.

The platform is API-first: any team can call `/v1/query` or `/v1/assure` exactly as they would call a model provider, and integrate the Trust Receipt into their own audit workflows.

---

## Live Demo

**[https://veritrace-app.streamlit.app](https://veritrace-app.streamlit.app)**

| Tab | What to try |
|-----|-------------|
| **Chat** | Ask `What is the Tier 1 copay?` — get a grounded answer with citations, confidence, conflict resolution, and a full Trust Receipt. Try `Look up MBR-100042 atorvastatin coverage` to trigger a live database tool call. |
| **Upload Docs** | Upload any `.md` or `.txt` policy document — it is chunked, embedded, and instantly queryable. |
| **Assurance Scan** | Click **Run Assurance Scan** — runs 15 adversarial attacks across 5 classes, produces a Trust Score and per-class breakdown. |

---

## Architecture

```
User query
  │
  ├─ Input guardrails (injection block + scope classifier)
  ├─ PII/PHI redaction (regex → typed placeholders)
  │
  ├─ Intent router ──► action ──► MCP tool dispatcher
  │                               (lookup_coverage / file_inquiry)
  │                               verify-then-execute gate
  │
  └─► knowledge ──► Query rewrite (nano LLM)
                  ──► Wide retrieval top-20 (Chroma + tenant filter)
                  ──► Cross-encoder re-rank top-4
                  ──► Conflict resolution (effective_date + supersedes)
                  ──► Evidence sufficiency check
                  ──► Grounded generation (mini LLM, citations only)
                  ──► Output gate (domain refusal + groundedness)
                  ──► PII restore
                  ──► Trust Receipt → Audit store
```

**Key design decisions:**

- **Tenant isolation** — mandatory `tenant_id` metadata filter on every Chroma query; cross-tenant leakage is structurally impossible.
- **Calibrated abstention** — evidence sufficiency check before generation; system abstains rather than fabricating when best candidate falls below threshold.
- **Conflict resolution** — when multiple versions of a document exist, the pipeline detects the conflict, resolves to the newer `effective_date`, and discloses the resolution in the Trust Receipt.
- **MCP tool server** — in-process dispatcher exposing read and write tools behind a verify-then-execute gate; action intents route here instead of the knowledge pipeline.
- **Short-term memory** — `SessionMemory` (sliding 10-turn window) injects prior turns into generation for coherent follow-up answers.
- **Semantic cache** — cosine similarity ≥ 0.92 short-circuits the pipeline per tenant; `route="cached"` in the receipt.
- **Provider agnostic** — works with OpenAI (`gpt-5.4-mini` / `text-embedding-3-small`), Groq (free tier, `llama-3.3-70b`), or fully offline mock mode.

---

## API

```
POST /v1/query       Full pipeline → Trust Receipt
POST /v1/chat        Multi-turn chat with session memory
POST /v1/assure      Adversarial scan → Trust Score + AssuranceReport
GET  /v1/tools       List available MCP tool definitions
GET  /v1/receipts/{id}  Retrieve a sealed Trust Receipt by ID
GET  /v1/sources     List indexed sources for a tenant
GET  /v1/usage       Aggregate token / cost / latency usage
```

**Trust Receipt — full response schema:**

```json
{
  "request_id": "rq_4a1b2c3d4e5f",
  "tenant": "demo",
  "route": "knowledge",
  "answer": "Generic atorvastatin is covered at Tier 1 with a \\$10 copay [1].",
  "confidence": "well-grounded",
  "citations": [
    {
      "source_id": "formulary_2026",
      "section": "Statins",
      "score": 0.94,
      "excerpt": "Atorvastatin (generic) — Tier 1 — $10 copay"
    }
  ],
  "conflict":  { "detected": true, "description": "formulary_2024 superseded by formulary_2026", "resolved_to": "formulary_2026" },
  "redaction": { "applied": false, "types": [] },
  "refusal":   { "triggered": false, "reason": null },
  "action":    null,
  "groundedness_score": 0.87,
  "cost_usd": 0.0001,
  "latency_ms": 3241.0,
  "model_profile": "mini",
  "timestamp": "2026-06-08T14:22:01.443Z"
}
```

Run `uvicorn api.main:app --reload` and open `/docs` for the full interactive OpenAPI spec.

---

## Assurance Engine

The autonomous Assurance Engine generates domain-specific adversarial attacks from the live knowledge base and runs them through the full pipeline:

| Attack class | What it tests |
|---|---|
| `injection` | Prompt injection and jailbreak resistance |
| `pii_extraction` | Bulk member data exfiltration attempts |
| `out_of_scope` | Off-domain and clinical advice requests |
| `unanswerable` | Abstention on questions with no KB evidence |
| `contradiction` | Version conflict resolution accuracy |

Results are aggregated into a **Trust Score (0–100)** with per-class breakdown and per-attack receipts, surfaced live in the Assurance Scan tab.

---

## MCP Tool Server

Two verified tools are available for member-specific actions:

| Tool | Type | What it does |
|---|---|---|
| `lookup_coverage` | READ | Queries the member coverage database for drug tier, copay, and PA status |
| `file_inquiry` | WRITE | Creates a new coverage inquiry ticket; returns ticket ID |

Queries containing member IDs (`MBR-XXXXXX`) or action keywords are automatically routed to the tool dispatcher. The verify-then-execute gate validates parameters before any DB write. `ActionInfo` is included in the Trust Receipt.

---

## Local Setup

```bash
git clone https://github.com/hrithikeshsankineni/veritrace
cd veritrace
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env — choose one:
#   OpenAI: set OPENAI_API_KEY=sk-...  MOCK_LLM=false
#   Groq (free): set GROQ_API_KEY=gsk_...  leave OPENAI_API_KEY empty  MOCK_LLM=false
#   Offline: leave keys empty, MOCK_LLM=true (no API calls)

# Run the console (seeds synthetic data automatically)
streamlit run console/app.py

# Or run the API server
uvicorn api.main:app --reload

# Run all tests
python -m pytest

# Run the evaluation harness
python -m evals --mock   # offline
python -m evals          # against live LLM
```

---

## Project Structure

```
veritrace/
├── ingest/          Parsers (PDF, MD, TXT) + structure-aware chunker
├── index/           Embeddings + Chroma vector store (tenant-isolated)
├── retrieval/       Query rewrite + wide retrieval + cross-encoder re-rank
├── responder/       Evidence check + grounded generation + conflict resolution
├── safety/          Input guardrails + PII redaction + output gate
├── assurance/       Attack synthesis + runner + Trust Score
├── tools/           MCP tool server + verified action handlers
├── memory.py        Thread-safe session memory (sliding window)
├── cache.py         Semantic cache (cosine ≥ 0.92, LRU per tenant)
├── audit.py         SQLite audit store — persists every Trust Receipt
├── schemas.py       Pydantic models — TrustReceipt, Citation, ActionInfo, …
└── config.py        Environment settings + provider detection

api/                 FastAPI application (7 endpoints)
console/             Streamlit demo (Chat + Upload Docs + Assurance Scan)
data/                Synthetic regulated corpus + deterministic seed script
evals/               40-case golden dataset + evaluation harness
tests/               246 tests, all passing
```

---

## Test Suite

```
246 tests — all passing

Areas covered:
  LLM wrapper (mock + provider selection)
  Chunker (structure-aware, stable, metadata-preserving)
  Vector store (tenant isolation, embed + retrieve)
  Retrieval pipeline (rewrite, retrieve, re-rank)
  Evidence + generation (grounded output, citations)
  Safety (guardrails, redaction, output gate)
  Conflict resolution (effective_date, supersedes)
  MCP tools (extraction, verification, execution, routing)
  Assurance engine (attack synthesis, scoring)
  Session memory + semantic cache
  Eval harness structure (40 golden cases)
  API endpoints (query, chat, assure, receipts, usage)
```

---

## Design Documents

| Document | Contents |
|---|---|
| [System Design](Veritrace_System_Design.md) | Architecture, data flows, component specs, §6.11 Trust Receipt schema |
| [Problem, Data & Evaluation](Veritrace_Problem_Data_Evaluation.md) | Problem statement, dataset design, evaluation methodology |
| [Build Log](PROGRESS.md) | Full task-by-task build record with decisions and notes |
