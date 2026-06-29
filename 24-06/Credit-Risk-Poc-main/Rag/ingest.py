"""
ingest.py
Reads documents from rag/documents/, splits them into chunks,
embeds them locally, and stores them in a local ChromaDB vector store.

Usage:
    python rag/ingest.py
"""

import os
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import chromadb
from chromadb.utils import embedding_functions
from pypdf import PdfReader

# ---- Config ----
BASE_DIR = Path(__file__).resolve().parent
DOCS_DIR = BASE_DIR / "documents"
DB_DIR = BASE_DIR / "chroma_db"
COLLECTION_NAME = "credit_risk_docs"

CHUNK_SIZE = 600       # characters per chunk
CHUNK_OVERLAP = 100    # overlap between chunks

EMBED_MODEL_NAME = "all-MiniLM-L6-v2"

# Matches lines that start a new regulatory/document section.
# Split is done with a lookahead so the heading stays at the top of each section.
_HEADING_RE = re.compile(
    r"(?m)(?=^(?:"
    r"(?:Principle|Section|Appendix|Annex|Article|Chapter)\s+\d+"  # "Principle 1"
    r"|\d+\.\d*\s+\S"                                               # "1. Foo" / "1.1 Foo"
    r"|[A-Z][A-Z ,\-]{5,}\s*$"                                     # ALL-CAPS heading line
    r"|#{1,3}\s"                                                     # Markdown ##
    r"))"
)


def read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def read_pdf_file(path: Path) -> str:
    reader = PdfReader(str(path))
    text_parts = []
    for page in reader.pages:
        text = page.extract_text() or ""
        text_parts.append(text)
    return "\n".join(text_parts)


def load_documents(docs_dir: Path):
    docs = []
    if not docs_dir.exists():
        print(f"⚠️  Documents folder not found: {docs_dir}")
        return docs

    for path in sorted(docs_dir.rglob("*")):
        if path.is_dir():
            continue
        suffix = path.suffix.lower()
        try:
            if suffix in (".txt", ".md"):
                text = read_text_file(path)
            elif suffix == ".pdf":
                text = read_pdf_file(path)
            else:
                continue

            if text.strip():
                docs.append((str(path.relative_to(docs_dir)), text))
                print(f"📄 Loaded: {path.name} ({len(text)} chars)")
            else:
                print(f"⚠️  Empty/unreadable: {path.name}")
        except Exception as e:
            print(f"❌ Failed to read {path.name}: {e}")

    return docs


def _subchunk(text: str, chunk_size: int, overlap: int):
    """Split a single block of text into overlapping character chunks."""
    chunks = []
    start = 0
    text_len = len(text)
    while start < text_len:
        end = min(start + chunk_size, text_len)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == text_len:
            break
        start = end - overlap
    return chunks


def _heading_of(section: str) -> str:
    """Return the first non-empty line of a section as its heading label."""
    for line in section.splitlines():
        line = line.strip()
        if line:
            return line[:120]
    return ""


def section_aware_chunk(text: str, chunk_size: int, overlap: int):
    """
    Split text on regulatory section headings first, then sub-chunk any
    section that exceeds chunk_size.  Returns list of (chunk_text, heading).
    """
    raw_sections = _HEADING_RE.split(text)

    results = []
    for section in raw_sections:
        section = section.strip()
        if not section:
            continue
        heading = _heading_of(section)
        if len(section) <= chunk_size:
            results.append((section, heading))
        else:
            for sub in _subchunk(section, chunk_size, overlap):
                results.append((sub, heading))
    return results


def main():
    print("=" * 60)
    print("RAG INGESTION")
    print("=" * 60)

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    DB_DIR.mkdir(parents=True, exist_ok=True)

    documents = load_documents(DOCS_DIR)
    if not documents:
        print(f"\nNo documents found in {DOCS_DIR}")
        print("Add .txt, .md, or .pdf files there and re-run this script.")
        return

    all_chunks = []
    all_ids = []
    all_metadatas = []

    for filename, text in documents:
        chunks = section_aware_chunk(text, CHUNK_SIZE, CHUNK_OVERLAP)
        for i, (chunk, heading) in enumerate(chunks):
            all_chunks.append(chunk)
            all_ids.append(f"{filename}::chunk_{i}")
            all_metadatas.append({"source": filename, "chunk_index": i, "section": heading})

    print(f"\nTotal chunks: {len(all_chunks)}")
    print(f"Loading embedding model ({EMBED_MODEL_NAME})...")

    embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBED_MODEL_NAME
    )

    print("Connecting to local ChromaDB...")
    client = chromadb.PersistentClient(path=str(DB_DIR))

    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    collection = client.create_collection(
        name=COLLECTION_NAME,
        embedding_function=embed_fn,
    )

    print("Embedding and storing chunks (this may take a minute)...")
    batch_size = 64
    for i in range(0, len(all_chunks), batch_size):
        batch_docs = all_chunks[i:i + batch_size]
        batch_ids = all_ids[i:i + batch_size]
        batch_meta = all_metadatas[i:i + batch_size]
        collection.add(documents=batch_docs, ids=batch_ids, metadatas=batch_meta)
        print(f"  → stored {min(i + batch_size, len(all_chunks))}/{len(all_chunks)}")

    print("\n✅ Done. Vector store saved to:", DB_DIR)
    print(f"   Collection: {COLLECTION_NAME}")
    print(f"   Total chunks indexed: {len(all_chunks)}")


if __name__ == "__main__":
    main()
    