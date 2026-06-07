"""Veritrace — Streamlit console.

Imports the core package directly (no API server required).
Provides a chat interface with a full evidence panel.

Run with:
    streamlit run console/app.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import streamlit as st

# ---------------------------------------------------------------------------
# Path setup — make the repo root importable when running from any cwd
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# ---------------------------------------------------------------------------
# Core initialisation (cached; runs once per Streamlit process)
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner="Loading knowledge base…")
def _init_pipeline():
    """Initialise the vector store and audit store once per process."""
    from data.seed import seed, SYNTHETIC_DIR
    from veritrace.audit import AuditStore
    from veritrace.config import settings
    from veritrace.index.embeddings import embed_chunks
    from veritrace.index.store import VectorStore
    from veritrace.ingest.chunker import chunk as chunk_doc
    from veritrace.ingest.parsers import parse

    if not SYNTHETIC_DIR.exists() or not list(SYNTHETIC_DIR.glob("*.md")):
        seed()

    store = VectorStore(
        collection_name="veritrace_console",
        persist_directory=str(_REPO_ROOT / "chroma_console"),
    )

    if store.count(settings.default_tenant) == 0:
        for md_file in sorted(SYNTHETIC_DIR.glob("*.md")):
            doc = parse(md_file)
            doc["metadata"]["tenant_id"] = settings.default_tenant
            chunks = chunk_doc(doc)
            if chunks:
                store.add(chunks, embed_chunks(chunks))

    audit = AuditStore(db_path=str(_REPO_ROOT / "console_audit.sqlite"))
    return store, audit


def _run_query(query: str, tenant_id: str, store, audit):
    """Run the full Veritrace pipeline and return a TrustReceipt."""
    from veritrace.responder.agent import answer
    from veritrace.safety.guardrails import check_input
    from veritrace.safety.output_gate import check_output
    from veritrace.safety.redaction import redact, restore
    from veritrace.schemas import RedactionInfo, RefusalInfo, TrustReceipt

    t0 = time.time()

    guard = check_input(query)
    if not guard["allowed"]:
        receipt = TrustReceipt(
            tenant=tenant_id,
            route="refused",
            answer=guard["blocked_reason"] or "Request blocked.",
            confidence="abstained",
            refusal=RefusalInfo(triggered=True, reason=guard["blocked_reason"]),
            latency_ms=round((time.time() - t0) * 1000, 1),
        )
        audit.persist_receipt(receipt)
        return receipt

    redacted_query, redact_ctx = redact(query)
    receipt = answer(redacted_query, tenant_id, store, start_time=t0)

    gate = check_output(receipt.answer, redacted_query, [])
    if not gate["passed"]:
        receipt = TrustReceipt(
            tenant=tenant_id,
            route="refused",
            answer=gate["reason"] or "Output blocked.",
            confidence="abstained",
            refusal=RefusalInfo(triggered=True, reason=gate["reason"]),
            latency_ms=round((time.time() - t0) * 1000, 1),
        )
        audit.persist_receipt(receipt)
        return receipt

    if redact_ctx.applied:
        receipt = receipt.model_copy(
            update={
                "answer": restore(receipt.answer, redact_ctx),
                "redaction": RedactionInfo(
                    applied=True, types=redact_ctx.types_detected
                ),
            }
        )

    audit.persist_receipt(receipt)
    return receipt


# ---------------------------------------------------------------------------
# Evidence panel renderer
# ---------------------------------------------------------------------------

def _render_receipt(receipt) -> None:
    """Render the evidence panel for a TrustReceipt."""
    conf = receipt.confidence
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Confidence", conf.replace("-", " ").title())
    col2.metric("Latency", f"{receipt.latency_ms:.0f} ms")
    col3.metric("Cost", f"${receipt.cost_usd:.4f}")
    col4.metric("Groundedness", f"{receipt.groundedness_score:.0%}")

    if receipt.refusal.triggered:
        st.warning(f"⛔ Blocked: {receipt.refusal.reason}")

    if receipt.redaction.applied:
        st.info(f"🔒 PII redacted: {', '.join(receipt.redaction.types)}")

    if receipt.conflict.detected:
        st.warning(f"⚠️ Conflict detected: {receipt.conflict.description}")

    if receipt.citations:
        with st.expander("📚 Citations", expanded=False):
            for i, c in enumerate(receipt.citations, 1):
                st.markdown(
                    f"**[{i}]** `{c.source_id}`"
                    + (f" — *{c.section}*" if c.section else "")
                    + f" (score: {c.score:.2f})"
                )
                if c.excerpt:
                    st.caption(f"> {c.excerpt}")

    with st.expander("🧾 Trust Receipt", expanded=False):
        st.json(receipt.model_dump(mode="json"))


# ---------------------------------------------------------------------------
# Page layout
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Veritrace",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🔍 Veritrace")
st.caption("Grounded, cited answers over your private knowledge base — with a Trust Receipt.")

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("Settings")
    tenant_id = st.text_input("Tenant ID", value="demo")

    st.markdown("---")
    st.markdown("**Sample questions:**")
    samples = [
        "Is generic atorvastatin covered?",
        "What is the copay for Tier 1 drugs?",
        "Do I need prior authorization for biologics?",
        "What is my annual deductible?",
        "Is dental implant surgery covered?",
        "How do I file a claim?",
    ]
    for q in samples:
        if st.button(q, key=f"sample_{q[:20]}", use_container_width=True):
            st.session_state["prefill"] = q

    st.markdown("---")
    from veritrace.config import settings
    st.info(f"Mode: {'**MOCK**' if settings.mock_llm else '**LIVE**'}")

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab_chat, tab_upload, tab_assure = st.tabs(["Chat", "Upload Docs", "Assurance Scan"])

# ---------------------------------------------------------------------------
# Tab 1 — Chat
# ---------------------------------------------------------------------------

with tab_chat:
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("receipt"):
                _render_receipt(msg["receipt"])

    prefill = st.session_state.pop("prefill", "")
    user_input = st.chat_input("Ask about your health plan coverage…") or prefill

    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        store, audit = _init_pipeline()
        with st.chat_message("assistant"):
            with st.spinner("Searching knowledge base…"):
                receipt = _run_query(user_input, tenant_id, store, audit)
            st.markdown(receipt.answer)
            _render_receipt(receipt)

        st.session_state.messages.append({
            "role": "assistant",
            "content": receipt.answer,
            "receipt": receipt,
        })

# ---------------------------------------------------------------------------
# Tab 2 — Upload Docs
# ---------------------------------------------------------------------------

with tab_upload:
    st.subheader("Upload Documents")
    st.caption(
        "Upload Markdown (.md) or plain text (.txt) files to add them to the "
        "knowledge base for the selected tenant. Documents are chunked, embedded, "
        "and indexed immediately."
    )

    uploaded_files = st.file_uploader(
        "Choose files",
        type=["md", "txt"],
        accept_multiple_files=True,
        key="doc_uploader",
    )

    source_id_input = st.text_input(
        "Source ID (optional — used for citations)",
        placeholder="e.g. policy_2026_q3",
    )
    authority = st.selectbox("Authority level", ["primary", "secondary", "reference"])
    effective_date = st.date_input("Effective date")

    if st.button("Ingest Documents", type="primary", disabled=not uploaded_files):
        from veritrace.ingest.chunker import chunk as chunk_doc
        from veritrace.index.embeddings import embed_chunks

        store, _ = _init_pipeline()
        total_chunks = 0
        progress = st.progress(0)

        for i, uf in enumerate(uploaded_files):
            raw = uf.read().decode("utf-8", errors="replace")
            # Build a minimal parsed doc dict
            fname = uf.name
            sid = source_id_input.strip() or fname.replace(" ", "_").lower()
            if len(uploaded_files) > 1:
                sid = f"{sid}_{i+1}" if source_id_input else sid

            doc = {
                "text": raw,
                "metadata": {
                    "source_id": sid,
                    "tenant_id": tenant_id,
                    "title": fname,
                    "authority_level": authority,
                    "effective_date": str(effective_date),
                    "doc_type": "uploaded",
                },
            }
            from veritrace.ingest.chunker import chunk as _chunk_doc
            chunks = _chunk_doc(doc)
            if chunks:
                store.add(chunks, embed_chunks(chunks))
                total_chunks += len(chunks)
            progress.progress((i + 1) / len(uploaded_files))

        progress.empty()
        st.success(
            f"Ingested {len(uploaded_files)} file(s) → {total_chunks} chunks "
            f"added to tenant **{tenant_id}**."
        )
        st.info(f"Knowledge base now has {store.count(tenant_id)} total chunks.")

    st.markdown("---")
    st.markdown("**Current knowledge base**")
    store, _ = _init_pipeline()
    st.metric("Total chunks indexed", store.count(tenant_id))


# ---------------------------------------------------------------------------
# Tab 3 — Assurance Scan
# ---------------------------------------------------------------------------

with tab_assure:
    st.subheader("Assurance Engine")
    st.caption(
        "Runs a battery of adversarial attacks through the full pipeline and "
        "scores how well the system defends against each class."
    )

    if st.button("Run Assurance Scan", type="primary", use_container_width=False):
        from veritrace.assurance.attacks import generate_attacks
        from veritrace.assurance.runner import run_attacks
        from veritrace.assurance.score import compute_score

        store, _ = _init_pipeline()
        attacks = generate_attacks(tenant_id)

        progress_bar = st.progress(0, text="Running attacks…")
        results_placeholder = st.empty()
        rows: list[dict] = []

        with st.spinner(""):
            results = run_attacks(attacks, tenant_id, store)

        progress_bar.empty()

        # Trust Score headline
        report = compute_score(results, tenant_id)
        score_color = "green" if report.trust_score >= 80 else ("orange" if report.trust_score >= 50 else "red")
        st.markdown(
            f"### Trust Score: :{score_color}[**{report.trust_score:.1f} / 100**]"
        )

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Attacks", report.total_attacks)
        col2.metric("Passed", report.passed, delta=None)
        col3.metric("Failed", report.failed, delta=None)

        # Per-class breakdown
        st.markdown("#### Per-class results")
        cls_cols = st.columns(len(report.per_class))
        for i, (cls, data) in enumerate(sorted(report.per_class.items())):
            s = data["score"]
            color = "green" if s == 100 else ("orange" if s >= 50 else "red")
            cls_cols[i].metric(
                cls.replace("_", " ").title(),
                f"{s:.0f}%",
                f"{data['passed']}/{data['total']}",
            )

        # Attack-level results
        st.markdown("#### Attack results")
        for r in results:
            icon = "✅" if r.passed else "❌"
            label = f"{icon} `{r.attack_id}` — **{r.attack_class}**"
            with st.expander(label, expanded=not r.passed):
                st.markdown(f"**Prompt:** {r.prompt}")
                st.markdown(f"**Result:** {r.notes}")
                st.caption("Trust Receipt")
                st.json(r.receipt.model_dump(mode="json"))

        # Findings
        if report.findings:
            st.markdown("#### Findings")
            for f in report.findings:
                st.error(f)
