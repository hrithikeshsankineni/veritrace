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
# Chat history
# ---------------------------------------------------------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("receipt"):
            _render_receipt(msg["receipt"])

# ---------------------------------------------------------------------------
# Input + pipeline
# ---------------------------------------------------------------------------

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
