# Veritrace
**Every answer, traceable to its source**

**[Live demo → https://veritrace-app.streamlit.app](https://veritrace-app.streamlit.app)**

---

## What it is

AI deployments in regulated organizations stall because there is no continuous, auditable proof that the system is safe, grounded, and compliant. Veritrace answers questions over a private knowledge base and issues a sealed **Trust Receipt** for every response — citing the exact source chunks, recording confidence, flagging conflicts, and logging cost and latency. When evidence is insufficient the system abstains rather than fabricating. A **PII/PHI redaction firewall** strips sensitive identifiers before any model call and restores them at the edge, so raw member data never reaches the LLM. An **autonomous Assurance Engine** continuously attacks the deployed system across five adversarial classes, scores the results, and produces a live **Trust Score (0–100)** — surfacing gaps before they become incidents. The entire system is API-first: any team can call `/v1/query` or `/v1/assure` from their own workflow exactly as they would call a model provider.

---

## Live demo

**[https://veritrace-app.streamlit.app](https://veritrace-app.streamlit.app)**

| Tab | What it shows |
|-----|---------------|
| **Chat** | Ask a question; receive a grounded answer with inline citations, a confidence band, PII redaction record, groundedness score, cost, and latency — all captured in the Trust Receipt. |
| **Assurance Scan** | Run a live adversarial scan across injection, PII extraction, out-of-scope, unanswerable, and contradiction attack classes. Produces a Trust Score and per-class findings with expandable receipts for every attack. |

---

## Trust Score

A scan against the synthetic health-plan corpus produces **86.7 / 100** in the reference run. Two known gaps are surfaced by the engine:

**(a) Abstention threshold tuning.** The dental implant query retrieved an excluded-services chunk at relevance 0.447 — above the current 0.15 abstention threshold — and the system answered rather than abstaining. The threshold needs calibration against a golden holdout set.

**(b) Conflict resolution by effective date.** When both the 2024 and 2026 formulary versions are present in the index, the system does not yet prefer the newer document by `effective_date` metadata. The 2024 entry can surface over the 2026 entry.

Surfacing these gaps is exactly what the Assurance Engine is designed to do. Both are documented in the scale path of the system design and are the next build items (tasks 8.1+).

---

## API

| Endpoint | Description |
|----------|-------------|
| `POST /v1/query` | Full pipeline: guardrails → redaction → agent → gate → receipt |
| `POST /v1/assure` | Run adversarial scan → Trust Score + AssuranceReport |
| `GET /v1/receipts/{id}` | Retrieve a sealed Trust Receipt by ID |
| `GET /v1/sources` | List indexed sources for a tenant |
| `GET /v1/usage` | Aggregate token/cost/latency usage for a tenant |

**Trust Receipt response shape:**

```json
{
  "request_id": "rq_4a1b2c3d4e5f",
  "tenant": "demo",
  "route": "knowledge",
  "answer": "Generic atorvastatin is covered at Tier 1 with a $10 copay [1].",
  "confidence": "well-grounded",
  "citations": [
    {
      "source_id": "formulary_2026",
      "section": "Drug Coverage",
      "page": null,
      "score": 0.94,
      "excerpt": "Generic atorvastatin is covered at Tier 1 with a $10 copay."
    }
  ],
  "conflict": { "detected": false, "description": null, "resolved_to": null },
  "redaction": { "applied": false, "types": [] },
  "refusal": { "triggered": false, "reason": null },
  "action": null,
  "groundedness_score": 0.87,
  "cost_usd": 0.0004,
  "latency_ms": 312.4,
  "model_profile": "mini",
  "timestamp": "2026-06-07T14:22:01.443Z"
}
```

Run `uvicorn api.main:app --reload` and open `/docs` for the full interactive OpenAPI spec.

---

## Architecture

- **Source-aware deterministic chunking** with hierarchical parent links and governance metadata (authority level, effective date, supersedes).
- **Tenant-isolated vector retrieval** with mandatory `tenant_id` metadata filter on every Chroma query — cross-tenant leakage is structurally impossible.
- **Cross-encoder re-ranking**: wide first-stage retrieval (top 20) → precision re-rank (top 4).
- **Calibrated abstention**: evidence sufficiency check before generation; abstains rather than fabricating when the best candidate falls below threshold.
- **PII/PHI redaction firewall**: detect → typed placeholder → restore at edge; raw sensitive data never reaches `llm.complete`.
- **Groundedness gate**: mini-tier judge blocks any answer containing claims not supported by the retrieved passages.
- **Domain-refusal**: output gate escalates individualized clinical advice and out-of-bounds requests before release.
- **Autonomous Assurance Engine**: synthesizes domain-specific adversarial attacks across five classes, runs them through the live pipeline, and scores the results as a Trust Score.

---

## Local setup

```bash
git clone https://github.com/hrithikeshsankineni/veritrace
cd veritrace
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env: add OPENAI_API_KEY, set MOCK_LLM=true to run without keys
# For Groq (free): set GROQ_API_KEY=gsk_... and leave OPENAI_API_KEY empty
python data/seed.py
MOCK_LLM=true streamlit run console/app.py
# In a second terminal:
MOCK_LLM=true uvicorn api.main:app --reload
```

---

## Project structure

```
veritrace/      # Core package: ingest, retrieval, responder, safety, assurance, audit
api/            # FastAPI application and endpoint definitions
console/        # Streamlit demo client (Chat + Assurance Scan tabs)
data/           # Synthetic regulated corpus and deterministic seed script
evals/          # Golden dataset for offline evaluation harness
tests/          # pytest suite — 185 tests, all passing
```

---

## Design documents

- [System Design Document](Veritrace_System_Design.md)
- [Problem, Data & Evaluation Document](Veritrace_Problem_Data_Evaluation.md)

---

## Build log

See [PROGRESS.md](PROGRESS.md) for the full build log — every task completed in order with decisions recorded and agent handoff notes.
