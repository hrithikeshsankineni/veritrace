# AGENTS.md — Veritrace build brief (single source of truth)

> **Read this file fully before doing anything.** It governs every coding agent working on this repo (Claude Code, Codex, or any other). The detailed product spec lives in `Veritrace_System_Design.md` and `Veritrace_Problem_Data_Evaluation.md` in the repo root — read both once for context. This file is the operational plan and the rules.

---

## 1. Mission

Build **Veritrace**, an API-first platform that answers questions over a private (synthetic) knowledge base and proves the answers are safe. It returns grounded, cited answers; abstains when evidence is insufficient; redacts sensitive data before any model sees it; and ships a **Trust Receipt** with every answer. A signature subsystem — the **Assurance Engine** — autonomously attacks the system and produces a **Trust Score**. A Streamlit console is the demo client of the API.

## 2. The deadline goal (2 days, must end with a LIVE public URL)

The single hard requirement: **a deployed, working public link** demonstrating the platform end-to-end. Build in this priority order and **deploy the core as soon as it works** — do not wait for the full system to deploy.

- **Minimum Live Product (MLP) — must ship:** synthetic data seeded → ingestion + structure-aware chunking → embeddings + tenant-scoped vector store → query rewrite + retrieval + cross-encoder re-rank → Responder (intent routing + evidence sufficiency + grounded generation + abstention) → input guardrails + PII redaction firewall + output groundedness gate → Trust Receipt + cost/latency metering + SQLite audit → Streamlit console (chat + evidence panel) → **deployed**.
- **Signature tier — strong target after MLP is live:** Assurance Engine (attack synthesis from the KB, run against `/query`, Trust Score + report) + an assurance dashboard in the console.
- **Enhancement tier — only if time remains:** cross-document conflict resolution, MCP tool server + one verified action, `/chat` short-term memory, semantic cache, scheduled assurance.

If you must cut, cut from the bottom. A deployed MLP beats a half-built full system.

## 3. Tech stack (do not substitute without noting it in PROGRESS.md)

- Python 3.11
- FastAPI + Uvicorn (API)
- ChromaDB (local vector store)
- OpenAI: **nano tier** for basic testing + lightweight classification (routing, topic checks, query rewrite); **mini tier** for generation, agent reasoning, evaluation/judging, and the Assurance Engine
- `text-embedding-3-small` (embeddings)
- `sentence-transformers` cross-encoder `cross-encoder/ms-marco-MiniLM-L-6-v2` (local re-ranker)
- SQLite (audit + telemetry)
- Streamlit (console / demo client)
- `mcp` Python SDK (tool server, enhancement tier only)

Keep dependencies lean. Prefer the standard library and the packages above. Do not add a dependency without a reason recorded in PROGRESS.md.

## 4. Canonical repo structure (create exactly this; do not invent extra top-level dirs)

```
veritrace/
  README.md
  AGENTS.md
  CLAUDE.md
  PROGRESS.md
  Veritrace_System_Design.md
  Veritrace_Problem_Data_Evaluation.md
  .env.example
  .gitignore
  requirements.txt
  veritrace/                 # core package (importable, framework-agnostic)
    __init__.py
    config.py                # settings from env; MOCK_LLM flag; model tier names
    schemas.py               # pydantic models incl. TrustReceipt
    llm.py                   # OpenAI client wrapper: tiers + MOCK_LLM stubs
    ingest/parsers.py
    ingest/chunker.py        # structure-aware + hierarchical, deterministic
    index/embeddings.py
    index/store.py           # Chroma wrapper + mandatory tenant metadata filter
    retrieval/rewrite.py
    retrieval/retrieve.py
    retrieval/rerank.py
    responder/agent.py       # intent routing + loop
    responder/evidence.py    # sufficiency + (later) conflict detection
    responder/generate.py
    safety/guardrails.py     # injection + topic/scope (input)
    safety/redaction.py      # PII/PHI detect -> placeholder -> restore
    safety/output_gate.py    # groundedness gate + domain refusal
    audit.py                 # SQLite: persist + fetch Trust Receipts, telemetry
    cache.py                 # semantic cache (enhancement)
    memory.py                # short-term memory (enhancement)
    assurance/attacks.py     # attack synthesis from KB
    assurance/runner.py      # run attacks through /query
    assurance/score.py       # Trust Score + report
    tools/mcp_server.py      # MCP tool server (enhancement)
    tools/actions.py         # verified actions (enhancement)
  api/main.py                # FastAPI app: wires endpoints to core package
  console/app.py             # Streamlit; imports core directly (works even if API down)
  data/synthetic/            # generated corpus + records + member profiles
  data/seed.py               # generates the synthetic corpus deterministically
  evals/golden.jsonl         # gold dataset for scoring + judge validation
  tests/                     # pytest; one test file per core module
```

The core logic lives in `veritrace/` and must be importable with **no web framework dependency**. `api/` and `console/` are thin layers over it. This separation is what lets the console deploy and demo even if the API host is unavailable.

## 5. Config and secrets (keys are PLACEHOLDERS for now)

- All config comes from environment variables, read in `veritrace/config.py`. Never hardcode keys.
- Create `.env.example` with: `OPENAI_API_KEY=sk-REPLACE_ME`, `MINI_MODEL=gpt-5.4-mini`, `NANO_MODEL=gpt-5.4-nano`, `EMBED_MODEL=text-embedding-3-small`, `MOCK_LLM=true`.
- `.gitignore` must include `.env`, `__pycache__/`, `*.pyc`, `.venv/`, `chroma/`, `*.sqlite`, `data/synthetic/*` (keep `data/seed.py`).
- **`MOCK_LLM` flag is mandatory.** When `MOCK_LLM=true`, `veritrace/llm.py` returns deterministic stub responses instead of calling OpenAI, so the entire pipeline runs and tests pass **without real keys**. Build and test everything in mock mode now; flip to `false` once real keys arrive. Model names above are configurable; confirm exact strings against the OpenAI dashboard when keys are issued.

## 6. Build phases — work the tasks in PROGRESS.md in order

The ordered, commit-sized task list is in `PROGRESS.md`. Each task has a Definition of Done. Do tasks top to bottom. After finishing a task: run its tests, commit, and tick it in PROGRESS.md (see §8). Do not start a later phase before the current one's Definition of Done is met and committed.

## 7. Coding standards and hygiene (strict)

- **Clean and minimal.** Create only files in the structure above. No scratch files, no `test.py` in root, no commented-out code, no dead code, no unused dependencies. If you create a temp file, delete it before committing.
- **One responsibility per module.** Keep functions small and named clearly. Type-hint everything. Pydantic for all API and receipt schemas.
- **Do not touch unrelated code.** Only edit files relevant to the current task. Never refactor or reformat code outside your task's scope.
- **Deterministic where it matters.** Chunking and seeding must be deterministic (same input → same output) for auditability.
- **Tests with every module.** Add/adjust a pytest in `tests/` for each core module; tests must pass in `MOCK_LLM=true` mode.
- **Small, focused commits.** One task = one commit. Message format: `feat(retrieval): cross-encoder re-rank` / `fix(safety): restore placeholders at edge` / `test(ingest): chunker boundaries` / `chore: scaffold`.
- **No secrets, ever**, in code or commits.
- **Errors are handled, never swallowed.** Tool/model failures retry with backoff then degrade gracefully; never fabricate a result.

## 8. Collaboration protocol — Claude Code and Codex are one team

Two agents work this repo. They must never corrupt each other's work or duplicate effort. The mechanism:

1. **Shared brain = this file + `PROGRESS.md`.** Before starting *any* session, the active agent reads AGENTS.md and PROGRESS.md to know the plan and the current state.
2. **Single in-flight task.** Only one task is `IN PROGRESS` at a time. Before starting, mark the task `IN PROGRESS (<agent name>)` in PROGRESS.md and commit that change first. This is the lock — if a task is already `IN PROGRESS`, pick the next free task instead.
3. **Finish at clean boundaries.** Always complete a task fully (code + tests passing + committed) before stopping. Never hand off mid-file. This is what makes takeover seamless.
4. **Handoff on limit.** If an agent hits a usage limit or is interrupted, the work is already committed at a clean boundary and PROGRESS.md shows exactly what's done and what's next. The other agent resumes by reading PROGRESS.md and picking the next free task. No re-explanation needed.
5. **Update the log.** After each task: tick it `DONE`, add a one-line note under "Decisions/Notes" if you made any non-obvious choice or deviation. Commit.
6. **Same conventions.** Both agents follow the structure, standards, and commit format here, so the codebase reads as one author regardless of who wrote a part.
7. **No parallel edits to the same files.** Because tasks are modular and locked via PROGRESS.md, the two agents touch disjoint files. Respect the lock.

## 9. Definition of "done and live"

- `uvicorn api.main:app` serves the API locally; `/docs` shows the OpenAPI spec; `/v1/query` returns a valid Trust Receipt in `MOCK_LLM` mode and with real keys.
- `streamlit run console/app.py` runs the console; asking a question shows an answer + evidence panel; the Assurance scan (if built) shows a Trust Score.
- The console is **deployed to Streamlit Community Cloud** from this public repo → that URL is the live link.
- `pytest` passes.
- README documents setup, run, and the deployed URL.

## 10. Deployment plan

- **Primary live link:** deploy `console/app.py` to **Streamlit Community Cloud** (free, deploys from this GitHub repo, gives a public URL). It imports the core package directly, so it is fully functional standalone. Set `OPENAI_API_KEY` and `MOCK_LLM` in Streamlit Cloud secrets.
- **API hosting (secondary, for the "others can call it" story):** deploy `api/main.py` to Render or Railway free tier from the same repo if time allows; otherwise demonstrate the API via `/docs` locally in the demo video and document the deploy steps in README.
- Deploy the MLP the moment it works; redeploy as features land.

## 11. Hard guardrails for agents (do not violate)

- Do not commit real API keys or real personal data. All data is synthetic.
- Do not add cloud infra, auth servers, Docker orchestration, or paid services beyond what §3 lists.
- Do not expand scope beyond PROGRESS.md. New ideas go in PROGRESS.md "Backlog," not into the build.
- Do not delete or rewrite the two design docs or this file.
- If a task is ambiguous, make the smallest reasonable choice, note it in PROGRESS.md, and continue — do not stall.
