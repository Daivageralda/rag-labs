"""OpenRouter LLM wrapper — model fallback chain + prompt builder."""

import json
import time
import requests

from app.config import settings

MODELS = [
    # "meta-llama/llama-3.3-70b-instruct:free",
    # "nvidia/llama-3.1-nemotron-ultra-253b-v1:free",
    # "google/gemma-3-27b-it:free",
    # "microsoft/phi-4-reasoning-plus:free",
    "openrouter/auto",
]

_HEADERS = {
    "Authorization": f"Bearer {settings.openrouter_api_key}",
    "Content-Type": "application/json",
    "HTTP-Referer": "http://localhost:8000",
    "X-Title": "RAG-API",
}


def _is_rate_limit(result: dict) -> bool:
    err = result.get("error", {})
    if not err:
        return False
    code = str(err.get("code", ""))
    msg  = str(err.get("message", "")).lower()
    return (
        code in ("429", "rate_limit_exceeded")
        or "rate limit" in msg
        or "venice" in msg
        or "try again" in msg
    )


def call_model(model: str, messages: list, retries: int = 2) -> dict | None:
    """Call a single OpenRouter model. Returns raw API response or None on failure."""
    for attempt in range(retries):
        try:
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=_HEADERS,
                data=json.dumps({
                    "model": model,
                    "messages": messages,
                    "max_tokens": 1024,
                    "temperature": 0.7,
                    "provider": {"ignore": ["Venice"]},
                }),
                timeout=45,
            )
            if resp.status_code == 429:
                wait = 3 * (attempt + 1)
                print(f"[LLM] 429 ({model}), retry in {wait}s...")
                time.sleep(wait)
                continue
            if resp.status_code != 200:
                print(f"[LLM] HTTP {resp.status_code} ({model}): {resp.text[:150]}")
                return None
            result = resp.json()
            if "error" in result:
                print(f"[LLM] Error body ({model}): {result['error'].get('message','')}")
                if _is_rate_limit(result):
                    time.sleep(3 * (attempt + 1))
                    continue
                return None
            return result
        except requests.exceptions.Timeout:
            print(f"[LLM] Timeout attempt {attempt+1} ({model})")
            time.sleep(2)
        except Exception as e:
            print(f"[LLM] Exception ({model}): {e}")
            return None
    return None


def complete(messages: list) -> dict:
    """Try models in order. Always returns {"answer": str, "model": str}."""
    for model in MODELS:
        print(f"[LLM] Trying: {model}")
        result = call_model(model, messages)
        if result is None:
            continue
        choices = result.get("choices", [])
        if not choices:
            continue
        content = choices[0].get("message", {}).get("content", "").strip()
        if content:
            used = result.get("model", model)
            print(f"[LLM] OK — {used}")
            return {"answer": content, "model": used}
    return {
        "answer": "⚠️ Semua model sedang tidak tersedia. Coba lagi dalam beberapa menit.",
        "model": "none",
    }


def is_person_query(query: str) -> bool:
    """Heuristic to detect queries about a specific person."""
    q = query.lower()
    triggers = [
        "siapa", "who is", "who are", "profil", "profile",
        "biodata", "biografi", "biography", "lahir", "born",
        "umur", "age", "pekerjaan", "jabatan", "karir", "career",
        "istri", "suami", "anak", "keluarga", "spouse", "children",
        "tokoh", "artis", "aktor", "aktris", "politikus", "politician",
        "ceo", "founder", "pendiri",
    ]
    return any(t in q for t in triggers)


def _format_scraper_answer(query: str, context_docs: list) -> dict:
    """Summarize scraped web results via LLM for cleaner person query output."""
    web_docs = [d["text"] for d in context_docs if d.get("source") == "general"]
    if not web_docs:
        return {
            "answer": f"Maaf, tidak ditemukan informasi tentang \"{query}\" dari hasil pencarian web.",
            "model": "scraper",
        }

    combined = "\n\n---\n\n".join(web_docs[:3])
    if len(combined) > 4000:
        combined = combined[:4000] + "..."

    prompt = f"""Kamu adalah asisten yang merangkum informasi dari internet.

Berikut hasil pencarian web untuk pertanyaan: "{query}"

{combined}

Tugas:
- Rangkum informasi di atas menjadi jawaban yang informatif, terstruktur, dan enak dibaca
- Sertakan fakta-fakta penting (nama lengkap, profesi, tanggal lahir, pencapaian, dll) jika ada
- Tulis dalam bahasa yang sama dengan pertanyaan user
- Jangan tambahkan informasi yang tidak ada di sumber di atas"""

    return complete([{"role": "user", "content": prompt}])


def generate_answer(query: str, context_docs: list, history: list) -> dict:
    """Build RAG prompt and call LLM. Returns {"answer": str, "model": str}."""
    # Person queries → skip LLM, return scraped results directly
    if is_person_query(query):
        print(f"[LLM] Person query detected, bypassing LLM: {query[:60]}")
        return _format_scraper_answer(query, context_docs)

    personal = [d["text"] for d in context_docs if d.get("source") == "personal"]
    general  = [d["text"] for d in context_docs if d.get("source") != "personal"]

    history_text = "\n".join(
        f"User: {h['query']}\nAssistant: {h['answer']}" for h in history
    ) or "Belum ada riwayat percakapan."

    sections = []
    if personal:
        sections.append(
            "[KONTEKS PERSONAL USER]\n"
            "(Data pribadi — struk belanja, dokumen upload. JANGAN tampilkan ke user lain.)\n"
            + "\n\n---\n\n".join(personal[:3])
        )
    if general:
        sections.append(
            "[KONTEKS UMUM]\n"
            "(Pengetahuan publik — artikel web, informasi umum.)\n"
            + "\n\n---\n\n".join(general[:3])
        )

    context_block = "\n\n".join(sections) if sections else "Tidak ada konteks tersedia."

    prompt = f"""Kamu adalah AI assistant berbasis RAG.

[RIWAYAT PERCAKAPAN]
{history_text}

{context_block}

[PERTANYAAN]
{query}

Panduan:
- Gunakan konteks personal untuk pertanyaan tentang data pribadi user (struk, pembelian, dll)
- Gunakan konteks umum untuk pertanyaan pengetahuan umum
- Jangan campur informasi personal dengan informasi umum"""

    return complete([{"role": "user", "content": prompt}])
