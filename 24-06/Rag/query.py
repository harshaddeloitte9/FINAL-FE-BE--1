"""
query.py
Retrieves relevant chunks from the local ChromaDB vector store
and generates an answer using a local Ollama LLM.

Usage:
    python rag/query.py "your question here"
    or run with no args for interactive mode.
"""

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import chromadb
from chromadb.utils import embedding_functions
import ollama

# ---- Config ----
BASE_DIR = Path(__file__).resolve().parent
DB_DIR = BASE_DIR / "chroma_db"
COLLECTION_NAME = "credit_risk_docs"

EMBED_MODEL_NAME = "all-MiniLM-L6-v2"
LLM_MODEL_NAME = "llama3.1"
TOP_K = 8


def get_collection():
    embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBED_MODEL_NAME
    )
    client = chromadb.PersistentClient(path=str(DB_DIR))
    return client.get_collection(name=COLLECTION_NAME, embedding_function=embed_fn)


def retrieve(collection, question: str, top_k: int = TOP_K):
    results = collection.query(query_texts=[question], n_results=top_k)
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    return list(zip(docs, metas))


def build_prompt(question: str, chunks):
    context_blocks = []
    for doc, meta in chunks:
        source = meta.get("source", "unknown")
        context_blocks.append(f"[Source: {source}]\n{doc}")

    context = "\n\n---\n\n".join(context_blocks)

    prompt = f"""You are a helpful assistant answering questions based ONLY on the provided context.
If the answer isn't in the context, say you don't have enough information — do not make things up.

Context:
{context}

Question: {question}

Answer:"""
    return prompt


def ask_llm(prompt: str) -> str:
    response = ollama.chat(
        model=LLM_MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
    )
    return response["message"]["content"]


def answer_question(question: str):
    collection = get_collection()
    chunks = retrieve(collection, question)

    if not chunks:
        print("No relevant chunks found. Did you run ingest.py first?")
        return

    print("\n📚 Retrieved chunks from:")
    for doc, meta in chunks:
        preview = doc[:80].replace("\n", " ")
        section = meta.get("section", "")
        section_label = f" [{section}]" if section else ""
        print(f"   - {meta.get('source', 'unknown')} (chunk {meta.get('chunk_index')}){section_label}")
        print(f"     \"{preview}...\"")


    prompt = build_prompt(question, chunks)

    print("\n🤖 Generating answer with local LLM...\n")
    answer = ask_llm(prompt)
    print("=" * 60)
    print(answer)
    print("=" * 60)


def main():
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
        answer_question(question)
    else:
        print("RAG Query Tool (local) — type 'exit' to quit\n")
        while True:
            question = input("Question: ").strip()
            if question.lower() in ("exit", "quit"):
                break
            if not question:
                continue
            answer_question(question)
            print()


if __name__ == "__main__":
    main()
    