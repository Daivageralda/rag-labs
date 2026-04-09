"""ChromaDB vector store — save, dedup, search, and score."""

import os
import time
import hashlib
import logging

# Must be set before transformers/sentence_transformers are imported
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")

# Suppress standard Python loggers
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
logging.getLogger("transformers").setLevel(logging.ERROR)

import chromadb
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

# Suppress transformers' own internal logging system (separate from stdlib logging)
import transformers
transformers.logging.set_verbosity_error()

from app.config import settings

embed_model = SentenceTransformer('all-MiniLM-L6-v2', tokenizer_kwargs={"clean_up_tokenization_spaces": True})

_client = chromadb.CloudClient(
    api_key=settings.chroma_api_key,
    tenant=settings.chroma_tenant,
    database=settings.chroma_database,
)
collection = _client.get_or_create_collection(name="docs")


def chunk_text(text: str, size: int = 500) -> list[str]:
    return [text[i:i + size] for i in range(0, len(text), size)]


def _hash(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


def _is_duplicate(text: str, threshold: float = 0.95) -> bool:
    try:
        existing = collection.query(query_texts=[text], n_results=1)
        if existing["documents"] and existing["documents"][0]:
            sim = cosine_similarity(
                embed_model.encode([text]),
                embed_model.encode(existing["documents"][0])
            )[0][0]
            return sim > threshold
    except Exception:
        pass
    return False


def save_docs(texts: list[str], meta: dict = None) -> None:
    """Save texts to ChromaDB, skipping near-duplicates."""
    if not texts:
        return
    clean = [t for t in texts if not _is_duplicate(t)]
    if not clean:
        print("[CHROMA] All duplicates, skipping")
        return
    embeddings = embed_model.encode(clean).tolist()
    ids = [f"doc_{int(time.time())}_{i}" for i in range(len(clean))]
    metadatas = [{"hash": _hash(t), **(meta or {})} for t in clean]
    collection.add(documents=clean, embeddings=embeddings, ids=ids, metadatas=metadatas)
    print(f"[CHROMA] Saved {len(clean)}/{len(texts)} docs")


def build_context(query: str, user_id: str, external_docs: list[str]) -> list[dict]:
    """
    - personal (receipt): dari ChromaDB, filter user_id — data pribadi user
    - general (web):      dari ChromaDB, shared semua user — pengetahuan umum
    - external_docs:      hasil fresh scrape query ini, selalu disertakan
    """
    query_emb = embed_model.encode([query])
    personal_raw: list[str] = []
    general_raw: list[str]  = []

    try:
        count = collection.count()
        if count > 0:
            # Struk/receipt — hanya milik user ini
            if user_id:
                try:
                    res = collection.query(
                        query_embeddings=query_emb.tolist(),
                        n_results=min(3, count),
                        where={"$and": [
                            {"user_id": {"$eq": user_id}},
                            {"source":  {"$eq": "receipt"}},
                        ]},
                    )
                    personal_raw = res["documents"][0]
                except Exception as e:
                    print(f"[CHROMA PERSONAL] {e}")
            # Web scrape — shared, bisa dipakai semua user
            try:
                res = collection.query(
                    query_embeddings=query_emb.tolist(),
                    n_results=min(3, count),
                    where={"source": {"$eq": "web"}},
                )
                general_raw = res["documents"][0]
            except Exception as e:
                print(f"[CHROMA GENERAL] {e}")
    except Exception as e:
        print(f"[CHROMA] {e}")

    docs = (
        [{"text": d, "source": "personal"} for d in personal_raw]
        + [{"text": d, "source": "general"} for d in general_raw]
        + [{"text": d, "source": "general"} for d in external_docs]
    )
    if not docs:
        return []

    scored = []
    for doc in docs:
        emb   = embed_model.encode([doc["text"]])
        score = float(cosine_similarity(query_emb, emb)[0][0])
        if doc["source"] == "personal":
            score *= 1.5  # boost personal docs
        scored.append((doc["text"], doc["source"], score))

    top = sorted(scored, key=lambda x: x[2], reverse=True)[:5]
    return [{"text": d[0], "source": d[1]} for d in top]
