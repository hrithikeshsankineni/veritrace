# Veritrace

An API-first platform that answers questions over a private knowledge base and proves the answers are safe.

## Live Demo

**[https://veritrace.streamlit.app](https://veritrace.streamlit.app)** ← Streamlit Community Cloud (deployed)

## Overview

Veritrace returns grounded, cited answers; abstains when evidence is insufficient; redacts sensitive data before any model sees it; and ships a **Trust Receipt** with every answer.

Key capabilities:
- Structure-aware chunking + tenant-scoped vector retrieval
- Cross-encoder re-ranking (local, no API cost)
- Calibrated abstention (never fabricates when evidence is weak)
- PII/PHI redaction firewall (values never reach external models)
- Input guardrails (injection blocking + scope classification)
- Output gate (groundedness judge + clinical advice refusal)
- Trust Receipt — per-response provenance record (persisted to SQLite)
- Streamlit console with evidence panel (citations, confidence, cost, latency)

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env: set OPENAI_API_KEY or leave MOCK_LLM=true for mock mode
```

## Seed synthetic data

```bash
python data/seed.py
```

## Run the API

```bash
uvicorn api.main:app --reload
# Docs: http://localhost:8000/docs
```

## Run the console

```bash
streamlit run console/app.py
```

## Run tests

```bash
MOCK_LLM=true pytest
```

## Deployment — Streamlit Community Cloud

1. Push this repo to GitHub (public).
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app**.
3. Set **Main file path** to `console/app.py`.
4. Under **Advanced settings → Secrets**, add:
   ```toml
   MOCK_LLM = "true"
   OPENAI_API_KEY = "sk-REPLACE_ME"
   ```
5. Deploy. The public URL is the live link.

## Architecture

```
veritrace/          core package (framework-agnostic)
  config.py         settings from env; MOCK_LLM flag
  llm.py            OpenAI wrapper + deterministic mock stubs
  schemas.py        pydantic models incl. TrustReceipt
  ingest/           parsers + structure-aware chunker
  index/            embeddings + Chroma store (tenant-isolated)
  retrieval/        query rewrite + retrieve + cross-encoder rerank
  responder/        intent routing + evidence + grounded generation
  safety/           redaction + guardrails + output gate
  audit.py          SQLite: Trust Receipts + usage telemetry
api/main.py         FastAPI (wires endpoints to core)
console/app.py      Streamlit (imports core directly)
data/seed.py        synthetic corpus generator
tests/              pytest suite (163+ tests; all pass with MOCK_LLM=true)
```

See [Veritrace_System_Design.md](Veritrace_System_Design.md) and [Veritrace_Problem_Data_Evaluation.md](Veritrace_Problem_Data_Evaluation.md) for full documentation.
