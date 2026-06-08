"""Veritrace — Streamlit console.

Imports the core package directly (no API server required).
Provides a professional chat interface with a full evidence panel.

Run with:
    streamlit run console/app.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import streamlit as st

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# ---------------------------------------------------------------------------
# Page config — must be first Streamlit call
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Veritrace",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS — professional design system
# ---------------------------------------------------------------------------

st.markdown("""
<style>
/* ── Google Font ── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* ── Base ── */
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* ── Hide default Streamlit chrome ── */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header { visibility: hidden; }

/* ── App background ── */
.stApp {
    background-color: #f8fafc;
}

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
    border-right: 1px solid #334155;
}
section[data-testid="stSidebar"] * {
    color: #e2e8f0 !important;
}
section[data-testid="stSidebar"] .stTextInput input {
    background: #1e293b !important;
    border: 1px solid #475569 !important;
    color: #f1f5f9 !important;
    border-radius: 8px !important;
}
section[data-testid="stSidebar"] .stButton button {
    background: #1e3a5f !important;
    border: 1px solid #3b82f6 !important;
    color: #bfdbfe !important;
    border-radius: 8px !important;
    font-size: 0.8rem !important;
    padding: 0.3rem 0.6rem !important;
    transition: all 0.15s ease;
    text-align: left !important;
    width: 100%;
}
section[data-testid="stSidebar"] .stButton button:hover {
    background: #1d4ed8 !important;
    border-color: #60a5fa !important;
    color: #ffffff !important;
}

/* ── Header banner ── */
.vt-header {
    background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 60%, #1d4ed8 100%);
    border-radius: 16px;
    padding: 28px 36px;
    margin-bottom: 24px;
    display: flex;
    align-items: center;
    gap: 16px;
    box-shadow: 0 4px 24px rgba(15,23,42,0.18);
}
.vt-header-icon {
    font-size: 2.8rem;
    line-height: 1;
}
.vt-header-text h1 {
    margin: 0;
    font-size: 2rem;
    font-weight: 700;
    color: #ffffff;
    letter-spacing: -0.5px;
}
.vt-header-text p {
    margin: 4px 0 0;
    font-size: 0.92rem;
    color: #94a3b8;
    font-weight: 400;
}
.vt-badge {
    display: inline-block;
    background: #10b981;
    color: #ffffff;
    font-size: 0.68rem;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 20px;
    letter-spacing: 0.5px;
    margin-left: 8px;
    vertical-align: middle;
}
.vt-badge-mock {
    background: #f59e0b !important;
}

/* ── Tab styling ── */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    background: transparent;
    border-bottom: 2px solid #e2e8f0;
    padding-bottom: 0;
}
.stTabs [data-baseweb="tab"] {
    background: transparent;
    border: none;
    color: #64748b;
    font-weight: 500;
    font-size: 0.9rem;
    padding: 10px 20px;
    border-radius: 8px 8px 0 0;
}
.stTabs [aria-selected="true"] {
    background: #eff6ff !important;
    color: #1d4ed8 !important;
    border-bottom: 2px solid #1d4ed8 !important;
}

/* ── Chat messages ── */
.stChatMessage {
    background: #ffffff !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 12px !important;
    padding: 16px !important;
    margin-bottom: 12px !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.04) !important;
}
.stChatMessage[data-testid="chat-message-user"] {
    background: #eff6ff !important;
    border-color: #bfdbfe !important;
}

/* ── Evidence cards ── */
.vt-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 20px;
    margin: 12px 0;
    box-shadow: 0 1px 4px rgba(0,0,0,0.04);
}
.vt-card-title {
    font-size: 0.78rem;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    margin-bottom: 8px;
}

/* ── Metric tiles ── */
[data-testid="metric-container"] {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 14px 18px !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
[data-testid="metric-container"] label {
    color: #64748b !important;
    font-size: 0.75rem !important;
    font-weight: 600 !important;
    text-transform: uppercase;
    letter-spacing: 0.6px;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    color: #0f172a !important;
    font-size: 1.3rem !important;
    font-weight: 700 !important;
}

/* ── Confidence badge colors ── */
.conf-well { color: #059669 !important; font-weight: 700; }
.conf-partial { color: #d97706 !important; font-weight: 700; }
.conf-abstained { color: #9333ea !important; font-weight: 700; }
.conf-insufficient { color: #dc2626 !important; font-weight: 700; }

/* ── Trust Score ring ── */
.trust-score-big {
    font-size: 4rem;
    font-weight: 800;
    line-height: 1;
    letter-spacing: -2px;
}
.trust-score-green { color: #059669; }
.trust-score-amber { color: #d97706; }
.trust-score-red { color: #dc2626; }

/* ── Action route badge ── */
.route-badge {
    display: inline-block;
    font-size: 0.7rem;
    font-weight: 600;
    padding: 2px 10px;
    border-radius: 20px;
    letter-spacing: 0.4px;
}
.route-knowledge { background: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe; }
.route-action    { background: #f0fdf4; color: #059669; border: 1px solid #bbf7d0; }
.route-refused   { background: #fff1f2; color: #e11d48; border: 1px solid #fecdd3; }
.route-cached    { background: #faf5ff; color: #7c3aed; border: 1px solid #ddd6fe; }

/* ── Divider ── */
hr { border-color: #e2e8f0 !important; }

/* ── Upload area ── */
[data-testid="stFileUploader"] {
    background: #ffffff;
    border: 2px dashed #cbd5e1;
    border-radius: 12px;
    padding: 8px;
}
[data-testid="stFileUploader"]:hover {
    border-color: #3b82f6;
    background: #eff6ff;
}

/* ── Primary buttons ── */
.stButton button[kind="primary"] {
    background: linear-gradient(135deg, #1d4ed8, #2563eb) !important;
    border: none !important;
    border-radius: 8px !important;
    color: white !important;
    font-weight: 600 !important;
    padding: 10px 24px !important;
    font-size: 0.88rem !important;
    box-shadow: 0 2px 8px rgba(29,78,216,0.25) !important;
    transition: all 0.15s ease;
}
.stButton button[kind="primary"]:hover {
    box-shadow: 0 4px 16px rgba(29,78,216,0.35) !important;
    transform: translateY(-1px);
}

/* ── Expanders ── */
.streamlit-expanderHeader {
    background: #f8fafc !important;
    border-radius: 8px !important;
    font-size: 0.85rem !important;
    font-weight: 500 !important;
    color: #475569 !important;
}
.streamlit-expanderContent {
    border: 1px solid #e2e8f0 !important;
    border-top: none !important;
    border-radius: 0 0 8px 8px !important;
}

/* ── Citation item ── */
.citation-item {
    padding: 10px 14px;
    background: #f8fafc;
    border-left: 3px solid #3b82f6;
    border-radius: 0 8px 8px 0;
    margin: 6px 0;
    font-size: 0.85rem;
}
.citation-score {
    display: inline-block;
    background: #eff6ff;
    color: #1d4ed8;
    font-size: 0.72rem;
    font-weight: 600;
    padding: 1px 6px;
    border-radius: 4px;
    margin-left: 6px;
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Core initialisation
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner="Loading knowledge base…")
def _init_pipeline():
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
    receipt = answer(redacted_query, tenant_id, store, start_time=t0, original_query=query)

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
# Evidence panel
# ---------------------------------------------------------------------------

def _conf_class(conf: str) -> str:
    return {
        "well-grounded": "conf-well",
        "partially-grounded": "conf-partial",
        "abstained": "conf-abstained",
        "insufficient-evidence": "conf-insufficient",
    }.get(conf, "")


def _route_badge(route: str) -> str:
    label = route.replace("-", " ").title()
    return f'<span class="route-badge route-{route}">{label}</span>'


def _render_receipt(receipt) -> None:
    conf = receipt.confidence
    conf_label = conf.replace("-", " ").title()
    conf_cls = _conf_class(conf)

    # Route + confidence header row
    st.markdown(
        f'<div style="margin-bottom:14px; display:flex; align-items:center; gap:10px;">'
        f'{_route_badge(receipt.route)}'
        f'<span class="{conf_cls}" style="font-size:0.85rem;">{conf_label}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Metric row
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Latency", f"{receipt.latency_ms:.0f} ms")
    col2.metric("Cost", f"${receipt.cost_usd:.4f}")
    col3.metric("Groundedness", f"{receipt.groundedness_score:.0%}")
    col4.metric("Model", receipt.model_profile)

    # Alerts
    if receipt.refusal.triggered:
        st.error(f"**Blocked** — {receipt.refusal.reason}", icon="🚫")

    if receipt.redaction.applied:
        st.info(
            f"**PII redacted** — types detected: {', '.join(receipt.redaction.types)}",
            icon="🔒",
        )

    if receipt.conflict.detected:
        st.warning(
            f"**Version conflict resolved** — {receipt.conflict.description}",
            icon="⚠️",
        )

    # Action result card
    if receipt.action:
        ai = receipt.action
        status_icon = "✅" if ai.verified else "❌"
        st.markdown(
            f'<div class="vt-card">'
            f'<div class="vt-card-title">Tool Execution — {ai.tool}</div>'
            f'<div style="font-size:0.88rem; color:#0f172a;">'
            f'{status_icon} <strong>{"Verified & executed" if ai.verified else "Rejected"}</strong><br>'
            f'<span style="color:#475569;">{ai.result}</span>'
            f'</div></div>',
            unsafe_allow_html=True,
        )

    # Citations
    if receipt.citations:
        with st.expander(f"📚 Citations ({len(receipt.citations)})", expanded=False):
            for i, c in enumerate(receipt.citations, 1):
                score_pct = f"{c.score:.0%}"
                section_str = f" · *{c.section}*" if c.section else ""
                st.markdown(
                    f'<div class="citation-item">'
                    f'<strong>[{i}]</strong> <code>{c.source_id}</code>{section_str}'
                    f'<span class="citation-score">{score_pct}</span>'
                    + (f'<div style="color:#64748b; margin-top:4px; font-style:italic;">'
                       f'"{c.excerpt}"</div>' if c.excerpt else "")
                    + "</div>",
                    unsafe_allow_html=True,
                )

    # Full receipt
    with st.expander("🧾 Trust Receipt", expanded=False):
        st.json(receipt.model_dump(mode="json"))


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("""
    <div style="text-align:center; padding: 20px 0 8px;">
        <div style="font-size:2.2rem;">🔍</div>
        <div style="font-size:1.1rem; font-weight:700; color:#f1f5f9; letter-spacing:-0.3px;">Veritrace</div>
        <div style="font-size:0.72rem; color:#94a3b8; margin-top:2px;">Grounded · Cited · Verified</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<hr style="border-color:#334155; margin:8px 0 16px;">', unsafe_allow_html=True)

    st.markdown('<div style="font-size:0.75rem; font-weight:600; color:#94a3b8; text-transform:uppercase; letter-spacing:0.8px; margin-bottom:8px;">Tenant</div>', unsafe_allow_html=True)
    tenant_id = st.text_input("Tenant ID", value="demo", label_visibility="collapsed")

    st.markdown('<hr style="border-color:#334155; margin:16px 0 12px;">', unsafe_allow_html=True)
    st.markdown('<div style="font-size:0.75rem; font-weight:600; color:#94a3b8; text-transform:uppercase; letter-spacing:0.8px; margin-bottom:10px;">Sample Queries</div>', unsafe_allow_html=True)

    samples = [
        ("💊", "Is generic atorvastatin covered?"),
        ("💰", "What is the Tier 1 copay?"),
        ("📋", "Do I need prior auth for biologics?"),
        ("💵", "What is my annual deductible?"),
        ("🦷", "Is dental implant surgery covered?"),
        ("🔍", "Look up MBR-100042 atorvastatin coverage"),
        ("📝", "File inquiry for MBR-100042 — billing question"),
    ]
    for icon, q in samples:
        if st.button(f"{icon} {q}", key=f"sample_{q[:18]}", use_container_width=True):
            st.session_state["prefill"] = q

    st.markdown('<hr style="border-color:#334155; margin:16px 0 12px;">', unsafe_allow_html=True)

    from veritrace.config import settings as _cfg
    mode_label = "MOCK" if _cfg.mock_llm else "LIVE"
    badge_cls = "vt-badge-mock" if _cfg.mock_llm else "vt-badge"
    st.markdown(
        f'<div style="font-size:0.78rem; color:#94a3b8;">Provider <span class="{badge_cls}" style="font-size:0.68rem;">{mode_label}</span></div>',
        unsafe_allow_html=True,
    )
    if not _cfg.mock_llm:
        provider = "Groq" if _cfg.groq_api_key else "OpenAI"
        st.markdown(f'<div style="font-size:0.72rem; color:#64748b; margin-top:2px;">{provider}</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.markdown(
    f"""
    <div class="vt-header">
        <div class="vt-header-icon">🔍</div>
        <div class="vt-header-text">
            <h1>Veritrace <span class="{'vt-badge-mock' if _cfg.mock_llm else 'vt-badge'} vt-badge"
                style="font-size:0.6rem; vertical-align:middle; padding: 3px 10px;">
                {'MOCK' if _cfg.mock_llm else 'LIVE'}
            </span></h1>
            <p>Grounded, cited answers over your private knowledge base — with a sealed Trust Receipt on every response.</p>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab_chat, tab_upload, tab_assure = st.tabs(["💬 Chat", "📂 Upload Docs", "🛡️ Assurance Scan"])

# ---------------------------------------------------------------------------
# Tab 1 — Chat
# ---------------------------------------------------------------------------

with tab_chat:
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Render history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"].replace("$", "\\$"))
            if msg.get("receipt"):
                _render_receipt(msg["receipt"])

    prefill = st.session_state.pop("prefill", "")
    user_input = st.chat_input("Ask about your health plan coverage, or request a member lookup…") or prefill

    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        store, audit = _init_pipeline()
        with st.chat_message("assistant"):
            with st.spinner("Searching knowledge base…"):
                receipt = _run_query(user_input, tenant_id, store, audit)
            st.markdown(receipt.answer.replace("$", "\\$"))
            _render_receipt(receipt)

        st.session_state.messages.append({
            "role": "assistant",
            "content": receipt.answer,
            "receipt": receipt,
        })

    if st.session_state.messages:
        if st.button("Clear conversation", key="clear_chat"):
            st.session_state.messages = []
            st.rerun()

# ---------------------------------------------------------------------------
# Tab 2 — Upload Docs
# ---------------------------------------------------------------------------

with tab_upload:
    st.markdown("### Upload Documents")
    st.caption(
        "Upload Markdown (.md) or plain text (.txt) files to add them to the "
        "knowledge base for the selected tenant. Documents are chunked, embedded, "
        "and indexed immediately."
    )

    col_form, col_info = st.columns([2, 1])

    with col_form:
        uploaded_files = st.file_uploader(
            "Drop files here or click to browse",
            type=["md", "txt"],
            accept_multiple_files=True,
            key="doc_uploader",
        )

        col_a, col_b = st.columns(2)
        with col_a:
            source_id_input = st.text_input(
                "Source ID (optional)",
                placeholder="e.g. policy_2026_q3",
            )
        with col_b:
            authority = st.selectbox("Authority level", ["primary", "secondary", "reference"])

        effective_date = st.date_input("Effective date")

        if st.button("Ingest Documents", type="primary", disabled=not uploaded_files):
            from veritrace.index.embeddings import embed_chunks
            from veritrace.ingest.chunker import chunk as chunk_doc

            store, _ = _init_pipeline()
            total_chunks = 0
            progress = st.progress(0, text="Processing files…")

            for i, uf in enumerate(uploaded_files):
                raw = uf.read().decode("utf-8", errors="replace")
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
                chunks = chunk_doc(doc)
                if chunks:
                    store.add(chunks, embed_chunks(chunks))
                    total_chunks += len(chunks)
                progress.progress((i + 1) / len(uploaded_files), text=f"Processing {fname}…")

            progress.empty()
            st.success(
                f"Ingested **{len(uploaded_files)} file(s)** → **{total_chunks} chunks** "
                f"added to tenant `{tenant_id}`."
            )

    with col_info:
        st.markdown(
            '<div class="vt-card">'
            '<div class="vt-card-title">Knowledge Base</div>',
            unsafe_allow_html=True,
        )
        store, _ = _init_pipeline()
        count = store.count(tenant_id)
        st.metric("Chunks indexed", count)

        st.markdown(
            '<div style="font-size:0.78rem; color:#64748b; margin-top:12px;">'
            '<strong>Supported formats</strong><br>'
            'Markdown (.md), Plain text (.txt)<br><br>'
            '<strong>Tip</strong><br>'
            'Use clear section headings for better chunk quality.'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Tab 3 — Assurance Scan
# ---------------------------------------------------------------------------

with tab_assure:
    st.markdown("### Assurance Engine")
    st.caption(
        "Runs a battery of adversarial attacks through the full pipeline and "
        "scores how well the system defends against each class."
    )

    col_run, col_info2 = st.columns([1, 2])
    with col_run:
        run_btn = st.button("▶ Run Assurance Scan", type="primary", use_container_width=True)
    with col_info2:
        st.markdown(
            '<div style="font-size:0.83rem; color:#64748b; padding:8px 0;">'
            '15 attacks across 5 classes: injection, PII extraction, out-of-scope, '
            'unanswerable, and contradiction traps.'
            '</div>',
            unsafe_allow_html=True,
        )

    if run_btn:
        from veritrace.assurance.attacks import generate_attacks
        from veritrace.assurance.runner import run_attacks
        from veritrace.assurance.score import compute_score

        store, _ = _init_pipeline()
        attacks = generate_attacks(tenant_id)

        with st.spinner("Running attack battery…"):
            results = run_attacks(attacks, tenant_id, store)

        report = compute_score(results, tenant_id)

        # ── Trust Score headline ──
        score = report.trust_score
        score_cls = "trust-score-green" if score >= 80 else ("trust-score-amber" if score >= 50 else "trust-score-red")
        grade = "A" if score >= 90 else ("B" if score >= 80 else ("C" if score >= 70 else ("D" if score >= 50 else "F")))

        st.markdown(
            f'<div class="vt-card" style="text-align:center; padding:32px;">'
            f'<div class="vt-card-title" style="text-align:center;">Trust Score</div>'
            f'<div class="trust-score-big {score_cls}">{score:.1f}</div>'
            f'<div style="color:#94a3b8; font-size:1rem; margin-top:4px;">/ 100 &nbsp;·&nbsp; Grade {grade}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # ── Headline metrics ──
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Attacks", report.total_attacks)
        m2.metric("Passed", report.passed)
        m3.metric("Failed", report.failed)

        # ── Per-class breakdown ──
        st.markdown("#### Per-class Results")
        cls_items = sorted(report.per_class.items())
        cls_cols = st.columns(len(cls_items))
        for i, (cls, data) in enumerate(cls_items):
            s = data["score"]
            delta_str = f"{data['passed']}/{data['total']}"
            cls_cols[i].metric(
                cls.replace("_", " ").title(),
                f"{s:.0f}%",
                delta_str,
            )

        # ── Findings ──
        if report.findings:
            st.markdown("#### Findings")
            for finding in report.findings:
                st.error(finding, icon="⚠️")

        # ── Attack results table ──
        st.markdown("#### Attack Results")
        for r in results:
            icon = "✅" if r.passed else "❌"
            cls_badge = f'<span class="route-badge route-knowledge" style="font-size:0.68rem;">{r.attack_class}</span>'
            label = f"{icon} `{r.attack_id}` {r.attack_class.replace('_',' ').title()}"
            with st.expander(label, expanded=not r.passed):
                st.markdown(
                    f'<div style="font-size:0.85rem; color:#475569; margin-bottom:8px;">'
                    f'<strong>Prompt:</strong> {r.prompt}</div>'
                    f'<div style="font-size:0.85rem; color:#0f172a;">'
                    f'<strong>Result:</strong> {r.notes}</div>',
                    unsafe_allow_html=True,
                )
                st.caption("Trust Receipt")
                st.json(r.receipt.model_dump(mode="json"))
