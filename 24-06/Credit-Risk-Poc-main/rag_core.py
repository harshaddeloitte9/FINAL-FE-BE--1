"""
rag_core.py
Core RAG engine: document ingestion, embedding, and retrieval.
Fully local — sentence-transformers (embeddings) + ChromaDB (vector store) + Ollama (LLM).
Storage root: rag_store/
"""

import re
import sys
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent
RAG_STORE_DIR = BASE_DIR / "rag_store"
DOCS_DIR = RAG_STORE_DIR / "documents"
DB_DIR = RAG_STORE_DIR / "chroma_db"
COLLECTION_NAME = "credit_risk_docs"

EMBED_MODEL = "all-MiniLM-L6-v2"
LLM_MODEL = "llama3.1"
CHUNK_SIZE = 600
CHUNK_OVERLAP = 100
TOP_K = 8

# Splits on regulatory heading patterns (Principle N, numbered sections, ALL-CAPS, Markdown ##)
_HEADING_RE = re.compile(
    r"(?m)(?=^(?:"
    r"(?:Principle|Section|Appendix|Annex|Article|Chapter)\s+\d+"
    r"|\d+\.\d*\s+\S"
    r"|[A-Z][A-Z ,\-]{5,}\s*$"
    r"|#{1,3}\s"
    r"))"
)


def _read_pdf(path: Path) -> str:
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    return "\n".join(p.extract_text() or "" for p in reader.pages)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _subchunk(text: str) -> list[str]:
    chunks, start = [], 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(text):
            break
        start = end - CHUNK_OVERLAP
    return chunks


def _section_chunks(text: str) -> list[tuple[str, str]]:
    """Split text into (chunk, heading) pairs using section-aware splitting."""
    results = []
    for section in _HEADING_RE.split(text):
        section = section.strip()
        if not section:
            continue
        heading = next((ln.strip()[:120] for ln in section.splitlines() if ln.strip()), "")
        if len(section) <= CHUNK_SIZE:
            results.append((section, heading))
        else:
            for sub in _subchunk(section):
                results.append((sub, heading))
    return results


class RAGCore:
    """
    Local RAG engine wrapping ChromaDB + sentence-transformers + Ollama.
    All storage lives under rag_store/.
    """

    def __init__(
        self,
        db_dir: Optional[str] = None,
        collection: str = COLLECTION_NAME,
        embed_model: str = EMBED_MODEL,
        llm_model: str = LLM_MODEL,
    ):
        import chromadb
        from chromadb.utils import embedding_functions

        self._db_dir = str(db_dir or DB_DIR)
        self._collection_name = collection
        self._llm_model = llm_model
        self._embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=embed_model
        )
        Path(self._db_dir).mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=self._db_dir)

    # ── Ingestion ────────────────────────────────────────────────────────────

    def ingest(self, docs_dir: Optional[str] = None, reset: bool = True) -> int:
        """
        Ingest all .txt/.md/.pdf files from docs_dir into ChromaDB.
        Returns the number of chunks indexed.
        """
        src = Path(docs_dir or DOCS_DIR)
        all_chunks, all_ids, all_metas = [], [], []

        for path in sorted(src.rglob("*")):
            if path.is_dir():
                continue
            suffix = path.suffix.lower()
            try:
                if suffix in (".txt", ".md"):
                    text = _read_text(path)
                elif suffix == ".pdf":
                    text = _read_pdf(path)
                else:
                    continue
                if not text.strip():
                    continue
                rel = str(path.relative_to(src))
                for i, (chunk, heading) in enumerate(_section_chunks(text)):
                    all_chunks.append(chunk)
                    all_ids.append(f"{rel}::chunk_{i}")
                    all_metas.append({
                        "source": rel,
                        "chunk_index": i,
                        "section": heading,
                    })
            except Exception as e:
                print(f"[RAGCore] Error reading {path.name}: {e}", file=sys.stderr)

        if not all_chunks:
            return 0

        col = self._get_collection(reset=reset)
        batch = 64
        for i in range(0, len(all_chunks), batch):
            col.add(
                documents=all_chunks[i:i + batch],
                ids=all_ids[i:i + batch],
                metadatas=all_metas[i:i + batch],
            )
        return len(all_chunks)

    # ── Retrieval ─────────────────────────────────────────────────────────────

    def retrieve(self, question: str, top_k: int = TOP_K) -> list[tuple[str, dict]]:
        """Return top_k (chunk_text, metadata) pairs for a question."""
        try:
            col = self._client.get_collection(
                name=self._collection_name, embedding_function=self._embed_fn
            )
        except Exception:
            return []
        results = col.query(query_texts=[question], n_results=top_k)
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        return list(zip(docs, metas))

    # ── Generation ────────────────────────────────────────────────────────────

    def ask(self, question: str, top_k: int = TOP_K) -> dict:
        """
        Full RAG pipeline: retrieve relevant chunks, build prompt, call local LLM.
        Returns {"answer": str, "chunks": list[dict]}.
        """
        import ollama as _ollama

        chunks = self.retrieve(question, top_k=top_k)
        if not chunks:
            return {"answer": "No relevant documents found. Have you run ingestion?", "chunks": []}

        context_blocks = []
        for doc, meta in chunks:
            source = meta.get("source", "unknown")
            section = meta.get("section", "")
            header = f"[Source: {source}]" + (f" [{section}]" if section else "")
            context_blocks.append(f"{header}\n{doc}")

        context = "\n\n---\n\n".join(context_blocks)
        prompt = (
            "You are a regulatory compliance expert answering questions based ONLY on the provided context. "
            "If the answer is not in the context, say you don't have enough information — do not make things up.\n\n"
            f"Context:\n{context}\n\nQuestion: {question}\n\nAnswer:"
        )

        response = _ollama.chat(
            model=self._llm_model,
            messages=[{"role": "user", "content": prompt}],
        )
        content = (
            response.message.content
            if hasattr(response, "message")
            else response["message"]["content"]
        )

        return {
            "answer": content,
            "chunks": [
                {
                    "text": doc[:200],
                    "source": meta.get("source"),
                    "section": meta.get("section", ""),
                    "chunk_index": meta.get("chunk_index"),
                }
                for doc, meta in chunks
            ],
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    @property
    def collection_exists(self) -> bool:
        try:
            self._client.get_collection(self._collection_name)
            return True
        except Exception:
            return False

    @property
    def chunk_count(self) -> int:
        try:
            col = self._client.get_collection(
                self._collection_name, embedding_function=self._embed_fn
            )
            return col.count()
        except Exception:
            return 0

    def _get_collection(self, reset: bool = False):
        if reset:
            try:
                self._client.delete_collection(self._collection_name)
            except Exception:
                pass
        try:
            return self._client.get_collection(
                name=self._collection_name, embedding_function=self._embed_fn
            )
        except Exception:
            return self._client.create_collection(
                name=self._collection_name, embedding_function=self._embed_fn
            )
