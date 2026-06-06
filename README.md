# Veritrace

An API-first platform that answers questions over a private knowledge base and proves the answers are safe.

## Overview

Veritrace returns grounded, cited answers; abstains when evidence is insufficient; redacts sensitive data before any model sees it; and ships a **Trust Receipt** with every answer. The **Assurance Engine** autonomously attacks the system and produces a **Trust Score**.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
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

## Deployed URL

*(Coming soon — will be updated after Streamlit Community Cloud deployment)*

## Architecture

- **veritrace/** — core package (importable, framework-agnostic)
- **api/** — FastAPI app wiring endpoints to core
- **console/** — Streamlit demo client (imports core directly)
- **data/** — synthetic corpus seed script
- **tests/** — pytest suite (all pass with `MOCK_LLM=true`)

See `Veritrace_System_Design.md` and `Veritrace_Problem_Data_Evaluation.md` for full design documentation.
