"""
rag_ui.py
Streamlit UI component for the RAG regulatory Q&A assistant.
Call render_rag_tab() from app.py or use standalone with: streamlit run rag_ui.py
"""

import streamlit as st
from pathlib import Path


def render_rag_tab() -> None:
    """Render the full RAG assistant panel (embed inside any Streamlit page)."""
    from rag_core import RAGCore, DOCS_DIR, DB_DIR, TOP_K

    st.markdown("""
    <div style='background:#1e293b; border-left:4px solid #6366f1;
                border-radius:0 8px 8px 0; padding:0.8rem 1.2rem; margin-bottom:1rem;'>
        <h3 style='margin:0; color:#e2e8f0;'>📚 Regulatory Q&A Assistant</h3>
        <p style='margin:0; color:#94a3b8; font-size:0.85rem;'>
            Ask questions about SS1/23, IFRS 9 and IFRS 7 — answers grounded in indexed documents
        </p>
    </div>
    """, unsafe_allow_html=True)

    # ── Status bar ────────────────────────────────────────────────────────────
    try:
        core = RAGCore()
        db_ready = core.collection_exists
        n_chunks = core.chunk_count if db_ready else 0
    except Exception as e:
        db_ready = False
        n_chunks = 0
        st.error(f"RAG engine unavailable: {e}")
        return

    stat_col, btn_col = st.columns([3, 1])
    with stat_col:
        if db_ready and n_chunks > 0:
            st.success(f"✅ Index ready — {n_chunks:,} chunks from `{DOCS_DIR.name}/`")
        else:
            st.warning(f"⚠️  No documents indexed yet. Add PDFs/TXTs to `{DOCS_DIR}` then click Ingest.")

    with btn_col:
        if st.button("📥 Ingest Documents", use_container_width=True, key="rag_ingest_btn"):
            with st.spinner("Ingesting regulatory documents…"):
                try:
                    core2 = RAGCore()
                    n = core2.ingest()
                    if n:
                        st.success(f"Indexed {n} chunks.")
                    else:
                        st.warning(f"No supported files found in {DOCS_DIR}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Ingestion failed: {e}")

    st.divider()

    # ── Question input ────────────────────────────────────────────────────────
    if "rag_history" not in st.session_state:
        st.session_state.rag_history = []

    top_k = st.slider("Chunks to retrieve (top-k)", 2, 12, TOP_K, 1, key="rag_topk")

    question = st.text_input(
        "Ask a regulatory question",
        placeholder="e.g. What are the five MRM principles?",
        key="rag_q_input",
    )

    ask_col, clear_col = st.columns([4, 1])
    with ask_col:
        ask_clicked = st.button("🔍 Ask", type="primary", use_container_width=True, key="rag_ask_btn")
    with clear_col:
        if st.button("🗑️ Clear", use_container_width=True, key="rag_clear_btn"):
            st.session_state.rag_history = []
            st.rerun()

    if ask_clicked and question.strip():
        if not db_ready or n_chunks == 0:
            st.error("Please ingest documents first.")
        else:
            with st.spinner("Searching documents and generating answer…"):
                try:
                    result = core.ask(question.strip(), top_k=top_k)
                    st.session_state.rag_history.insert(0, {
                        "question": question.strip(),
                        "answer": result["answer"],
                        "chunks": result.get("chunks", []),
                    })
                except Exception as e:
                    st.error(f"Query failed: {e}")

    # ── History ───────────────────────────────────────────────────────────────
    for item in st.session_state.rag_history:
        st.markdown(f"**Q:** {item['question']}")
        st.markdown(item["answer"])
        if item.get("chunks"):
            with st.expander(f"📄 Retrieved {len(item['chunks'])} source chunks"):
                for i, chunk in enumerate(item["chunks"], 1):
                    src = chunk.get("source", "unknown")
                    sec = chunk.get("section", "")
                    idx = chunk.get("chunk_index", "?")
                    preview = chunk.get("text", "")[:160].replace("\n", " ")
                    st.caption(f"**{i}. {src}** (chunk {idx})" + (f" [{sec[:60]}]" if sec else ""))
                    st.text(f'"{preview}..."')
        st.divider()


# ── Standalone entry point ───────────────────────────────────────────────────
if __name__ == "__main__":
    st.set_page_config(page_title="RAG Assistant", page_icon="📚", layout="wide")
    render_rag_tab()
