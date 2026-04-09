import os
from dotenv import load_dotenv

load_dotenv()


class _Settings:
    # LLM
    openrouter_api_key: str = os.environ.get("OPENROUTER_API_KEY", "")

    # Vector Store
    chroma_api_key: str  = os.environ.get("CHROMA_API_KEY", "")
    chroma_tenant: str   = os.environ.get("CHROMA_TENANT", "")
    chroma_database: str = os.environ.get("CHROMA_DATABASE", "rag-lab")

    # Web Search
    serpapi_api_key: str = os.environ.get("SERPAPI_API_KEY", "")  # kept for reference
    serper_api_key: str  = os.environ.get("SERPER_API_KEY", "")

    # WhatsApp (Waha)
    waha_url: str     = os.environ.get("WAHA_URL", "http://localhost:3000")
    waha_session: str = os.environ.get("WAHA_SESSION", "default")
    waha_api_key: str = os.environ.get("WAHA_API_KEY", "")

    # Storage
    receipts_dir: str = os.environ.get("RECEIPTS_DIR", "receipts")


settings = _Settings()
