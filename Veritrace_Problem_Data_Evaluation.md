# Veritrace — Problem Definition, Data Processing & Evaluation Criteria

**A self-auditing AI assurance platform for high-stakes knowledge work.**

| | |
|---|---|
| **Document** | Problem, Data & Evaluation Specification |
| **Version** | 1.0 |
| **Status** | Approved for build |
| **Last updated** | June 4, 2026 |
| **Reference deployment** | Regulated health-plan member services (synthetic data) |
| **Companion** | Veritrace — System Design Document |

---

# Part A — Problem Definition

## A.1 Background

Organizations in regulated industries — healthcare, insurance, finance, legal — hold large bodies of private knowledge (policies, formularies, procedures, contracts) and operate live systems of record. They want to put AI in front of this knowledge so employees and members get fast, accurate answers and routine actions get handled automatically.

They overwhelmingly cannot. AI assistants in these settings remain stuck in pilots. The blocker is not model quality; it is **assurance** — the inability to demonstrate, on an ongoing basis, that the AI is safe, honest, and compliant.

## A.2 The problem

A retrieval-based assistant that "answers from your documents with citations" appears to solve the problem but does not, for four compounding reasons:

1. **Contradiction and staleness.** Real knowledge bases contain documents that disagree — a current policy and a superseded one, two departments' guidance, a retracted procedure still in the store. Naive retrieval surfaces both and lets the model silently blend or arbitrarily choose, producing a citation-backed answer that is nonetheless wrong.
2. **Overconfidence.** When retrieval fails or the organization simply has no answer, a naive system answers anyway, fabricating a plausible response instead of declining.
3. **Sensitive-data exposure.** Questions and records routinely contain protected information; sending it to third-party models is a privacy and compliance hazard.
4. **Decay and adversarial pressure.** A system that was safe at launch drifts as knowledge changes, and faces a stream of adversarial inputs (injection, data-extraction, scope evasion) that a one-time review never anticipated.

In a regulated domain, each failure is not a UX defect but a **liability event**. The cost of a confident wrong answer is measured in compliance findings, clinical risk, and legal exposure — which is precisely why these deployments stall.

**Problem statement.** *Regulated organizations have no way to deploy AI over their private knowledge and systems while continuously proving that it answers safely, declines appropriately, protects sensitive data, and can be audited after the fact.*

## A.3 Why AI engineering is the right lever

The problem is not solvable by a better model alone; it requires **system engineering around the model**: deterministic retrieval and provenance, evidence-sufficiency and contradiction reasoning, data-masking by construction, policy-bound action, and an automated adversary that keeps the whole assembly honest over time. This is an AI-engineering problem, and the value lives in the engineering, not the model weights.

## A.4 Target users

| User | Need | What Veritrace gives them |
|---|---|---|
| **Member/employee (end user)** | A fast, correct answer or action over governed knowledge | Grounded answers, honest abstention, safe self-service actions |
| **Platform/AI engineer (builder)** | To embed trustworthy AI into their own product or workflow | An API with grounded answers and a machine-readable Trust Receipt |
| **Compliance / risk owner** | Evidence that the deployed AI is and remains safe | The Trust Score, assurance reports, and per-answer audit trail |
| **Operations owner** | Predictable cost and latency | Per-request metering and aggregate usage reporting |

## A.5 Representative use cases (reference deployment)

1. **Grounded knowledge answer** — "Is generic atorvastatin covered, and at what copay?" → cited answer from the current formulary, with a Trust Receipt.
2. **Contradiction handling** — a question whose answer differs between the 2024 and 2026 policy → the current answer, with the superseded version disclosed.
3. **Appropriate abstention** — a question the knowledge base does not cover → an explicit "no reliable basis to answer," not a guess.
4. **Out-of-bounds refusal** — a request for individualized clinical advice → declined and escalated.
5. **Verified action** — "open a ticket for my denied claim" → a confirmed, authorized, logged action via a connected system.
6. **Continuous assurance** — a scheduled scan that re-derives the Trust Score and flags any regression.

## A.6 Success criteria

The platform is successful if it: (a) answers in-scope questions with high measured groundedness; (b) abstains rather than fabricates when evidence is insufficient; (c) correctly resolves and discloses source conflicts; (d) leaks zero sensitive values to external models; (e) blocks the defined adversarial classes at a high rate; (f) seals an auditable receipt for every answer and action; and (g) reports cost and latency within target budgets. Quantitative targets are in Part C.

## A.7 Scope and non-goals

In scope: governed-knowledge answering, conflict/abstention handling, redaction, verified actions over simulated systems, continuous assurance, audit, metering, and a portable cross-domain configuration. Out of scope for the initial build: open-domain chat, model training, enterprise IAM, multi-region infrastructure, and real third-party integrations (interface is integration-ready).

---

# Part B — Data Processing

## B.1 Data sources

All data is **synthetic or public**, generated to resemble a regulated enterprise corpus, ensuring a realistic privacy/compliance profile with no real protected data in the system or repository.

| Source | Form | Role |
|---|---|---|
| Plan/formulary documents | PDF / Markdown | Primary knowledge corpus; includes deliberately versioned and conflicting entries |
| Policy & procedure manuals | Markdown / text | Knowledge corpus with authority levels and effective dates |
| Member-services FAQs | Markdown | Common-question coverage |
| Synthetic operational records | JSON / SQLite | Backing data for tool/action calls (tickets, coverage records) |
| Synthetic member profiles | JSON | Carriers of PII/PHI used to exercise the redaction firewall |
| Adversarial seed catalog | Generated | Attack templates the Assurance Engine specializes per knowledge base |

A second domain configuration (internal IT/HR helpdesk) is provided to demonstrate portability; the engine is unchanged.

## B.2 Data taxonomy and governance metadata

Every ingested unit carries: `tenant_id`, `source_id`, `doc_type`, `authority_level`, `effective_date`, `supersedes`, `section`, `page`. The authority/recency fields are mandatory inputs to conflict resolution; their presence is validated at ingestion, and units lacking them are flagged so the system can default to disclosure/abstention rather than silent resolution.

## B.3 Synthetic data generation

The corpus is generated to include the failure conditions the platform must handle: (a) **versioned conflicts** (same topic, different answers across effective dates), (b) **superseded-but-present** documents, (c) **coverage gaps** (plausible questions with no supporting document, to exercise abstention), and (d) **embedded sensitive values** in records and profiles (to exercise redaction). Generating these conditions deliberately is what makes the evaluation meaningful rather than cosmetic.

## B.4 Knowledge processing pipeline

Ingest → parse (format-aware) → annotate with governance metadata → segment with structure-aware, deterministic chunking → embed with a single consistent embedding model → index in the tenant-scoped vector store. Determinism is required end-to-end so that any citation can be reproduced exactly during audit. (Mechanics are detailed in the System Design Document.)

## B.5 Sensitive-data handling (PII/PHI)

**Principle: the model is structurally prevented from receiving raw sensitive data.**

1. **Detect** — incoming content (and retrieved records) are scanned for sensitive values: identifiers, contact details, member/account numbers, financial data. Pattern matching forms the first layer; a locally hosted classifier handles ambiguous cases.
2. **Mask** — detected values are replaced with typed placeholders before any external model call.
3. **Process** — the model reasons over placeholders only.
4. **Restore** — real values are reinstated at the response edge so the user receives a personalized answer.
5. **Never persist to third parties** — raw sensitive values never leave the trust boundary; only redaction *records* (which types were masked) are stored in the receipt, never the values themselves.

This flow is exercised on every assurance run and is itself a scored evaluation dimension (Part C).

## B.6 Guardrails (policy layer)

| Guardrail | Direction | Purpose |
|---|---|---|
| Prompt-injection detection | Input | Block attempts to override instructions or exfiltrate context. |
| Topic/scope control | Input | Refuse requests outside the configured domain. |
| Sensitive-data redaction | Input/Output | Mask on the way in, restore at the edge. |
| Groundedness gate | Output | Block answers not supported by cited evidence. |
| Domain-refusal | Output | Decline out-of-bounds requests (e.g. individualized clinical/legal/financial advice) and escalate. |

Guardrail policy is declared in the Knowledge Pack so it travels with the domain and is identical for the Responder and the Assurance Engine.

## B.7 Data lifecycle and isolation

Tenant data is isolated by mandatory metadata filtering at retrieval. Trust Receipts and telemetry are retained for audit; they record redaction *types*, not sensitive values. Synthetic data carries no retention or consent obligations, but the system is designed as though it does, so the controls transfer directly to a real deployment.

---

# Part C — Evaluation Criteria

## C.1 Evaluation philosophy

Evaluation is **continuous and adversarial, not a one-time pre-submission check.** The same harness that scores quality during development is given autonomy as the Assurance Engine and run on demand and on schedule against the live system. Quality is therefore a *measured, monitored property with a number attached*, not a claim.

## C.2 Evaluation dimensions and metrics

| Dimension | Metric(s) | What it answers |
|---|---|---|
| **Retrieval quality** | Recall@k, Mean Reciprocal Rank, context precision | Did the right evidence get retrieved and ranked? |
| **Answer faithfulness** | Groundedness/faithfulness rate (claims supported by cited evidence) | Is the answer actually supported? |
| **Answer relevance** | Answer-relevancy rate | Does the answer address the question asked? |
| **Abstention calibration** | Correct-abstention rate; false-answer rate on unanswerable items | Does it decline when it should? |
| **Conflict resolution** | Conflict-detection rate; correct-resolution rate | Does it catch and resolve contradictions correctly? |
| **Routing / tool selection** | Intent-routing accuracy; correct-tool-and-arguments rate | Did it choose RAG vs. the right action correctly? |
| **Action correctness** | Verified-action success rate; unauthorized-action rate (target 0) | Did it act correctly and only when permitted? |
| **Safety — injection** | Injection-block rate | Does it resist instruction-override attacks? |
| **Safety — data protection** | Sensitive-data leak rate (target 0) | Does any raw sensitive value reach the model or output? |
| **Safety — refusal** | Out-of-bounds refusal accuracy | Does it decline what it must decline? |
| **Cost** | Mean cost per request, by route | Is it economically viable? |
| **Latency** | p50 / p95 end-to-end and per stage | Is it fast enough? |

These roll up into the composite **Trust Score (0–100)** with transparent per-dimension breakdowns.

## C.3 Methodology

- **Golden dataset.** A curated set of ~30–50 cases spanning every dimension — grounded questions with known answers and expected citations, contradiction cases, unanswerable items, injection and data-extraction attempts, out-of-bounds requests, and action scenarios — each with an expected safe behavior. This set is version-controlled and is the ground truth for both development scoring and judge validation.
- **Automated judging.** A mini-tier model acts as judge for qualitative dimensions (faithfulness, relevance, refusal correctness). Each judge is **binary and single-purpose** — one judgment per call — to maximize reliability; judges are never asked to score multiple properties at once.
- **Judge validation.** Judge outputs are checked against the human-labeled golden subset to quantify and bound judge error, mitigating the shared-tier self-preference bias noted in the System Design Document.
- **Autonomous adversary.** The Assurance Engine synthesizes domain-specific attacks from the knowledge base (including contradiction traps from the org's own documents), executes them through the live request path, and scores outcomes — producing the Trust Score and a findings report.
- **Cadence.** Quality is scored on every meaningful change during build; assurance runs on demand for red-teaming and on a schedule for drift detection.

## C.4 Error handling and failure modes

| Failure | Detection | Response |
|---|---|---|
| Tool call fails or times out | Tool-server error / timeout | Bounded retry, then graceful degradation with an explicit notice; never fabricate a result. |
| Retrieval returns weak evidence | Sufficiency check below threshold | Abstain with calibrated confidence rather than answer. |
| Sources conflict | Consistency check | Resolve by authority/recency and disclose; abstain if indeterminate. |
| Draft answer unsupported | Groundedness gate fails | Block release; downgrade to abstention. |
| Sensitive value detected late | Redaction firewall | Mask before model; if detected at output, withhold and log. |
| Model/provider error | API error handling | Retry with backoff; surface a safe error, seal the failure in the receipt. |

Error handling is itself evaluated: failure scenarios are part of the golden set and the assurance suite.

## C.5 Cost and latency measurement

Every response records token counts, per-stage latency, and computed cost in its Trust Receipt; `GET /v1/usage` aggregates per tenant. Cost is controlled by the tiered model strategy (cheapest model per task) and the semantic cache; latency is budgeted per stage and monitored at p50/p95.

## C.6 Acceptance targets (initial)

| Metric | Target |
|---|---|
| Retrieval Recall@k | ≥ 0.85 |
| Answer groundedness rate | ≥ 0.95 |
| Correct-abstention rate (unanswerable items) | ≥ 0.90 |
| Conflict-detection rate | ≥ 0.85 |
| Intent-routing accuracy | ≥ 0.95 |
| Unauthorized actions | 0 |
| Injection-block rate | ≥ 0.95 |
| Sensitive-data leak rate | 0 |
| Out-of-bounds refusal accuracy | ≥ 0.95 |
| Mean cost / knowledge query (pre-cache) | ≤ ~$0.005 |
| Latency p95 (knowledge query) | ≤ ~3 s |
| Composite Trust Score | ≥ 85 |

Targets are initial and tuned against the golden dataset during build; the platform's own assurance reporting tracks them continuously thereafter.
