import os
import ssl
import logging

# ── Silence noisy library warnings before any heavy imports ────────────────
# 1. HF Hub: suppress "unauthenticated requests" warning
#    Set HF_TOKEN in .env to use your account's rate limits
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
logging.getLogger("huggingface_hub.utils._validators").setLevel(logging.ERROR)

# 2. sentence-transformers: suppress LOAD REPORT (benign arch mismatch note)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
logging.getLogger("transformers").setLevel(logging.ERROR)
# ───────────────────────────────────────────────────────────────────────────

# EasyOCR model download workaround for macOS SSL cert issue
ssl._create_default_https_context = ssl._create_unverified_context

from fastapi import FastAPI
from app.routers import chat, receipts, webhook
from app.rag import collection

app = FastAPI(title="RAG Chatbot API", version="2.0.0")

app.include_router(chat.router)
app.include_router(receipts.router)
app.include_router(webhook.router)


@app.get("/health")
def health():
    return {"status": "ok", "chroma_docs": collection.count()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
