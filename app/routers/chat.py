from fastapi import APIRouter

from app.models import QueryRequest
from app.memory import get_memory, update_memory
from app.scraper import search_and_scrape
from app.rag import build_context, save_docs, chunk_text
from app.llm import generate_answer, is_person_query

router = APIRouter()


@router.post("/chat")
def chat(req: QueryRequest):
    history  = get_memory(req.user_id)
    external = search_and_scrape(req.query)

    # Query umum → simpan sebagai referensi bersama semua user (tanpa user_id)
    # Query orang → tidak disimpan sama sekali
    if not is_person_query(req.query):
        chunks = []
        for doc in external:
            chunks.extend(chunk_text(doc))
        save_docs(chunks, meta={"source": "web"})

    docs   = build_context(req.query, req.user_id, external)
    result = generate_answer(req.query, docs, history)
    answer = result["answer"]

    update_memory(req.user_id, req.query, answer)

    return {
        "query"        : req.query,
        "answer"       : answer,
        "model_used"   : result["model"],
        "context_count": len(docs),
        "context"      : [
            {"text": d["text"][:100] + "...", "source": d["source"]}
            for d in docs
        ],
    }
