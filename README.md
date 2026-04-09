# RAG Chatbot API

Chatbot berbasis **Retrieval-Augmented Generation (RAG)** yang terintegrasi dengan WhatsApp via [Waha](https://waha.devlike.pro/). Mendukung pencarian web real-time, analisis struk belanja via OCR, dan memori percakapan per user.

---

## Fitur

- **RAG Pipeline** — kombinasi ChromaDB (vector store) + SerpAPI (web search) + LLM (OpenRouter)
- **WhatsApp Bot** — kirim/terima pesan teks dan gambar via Waha HTTP API
- **OCR Struk** — scan nota belanja dari foto, parse dengan LLM, simpan ke CSV
- **Memori Per User** — riwayat percakapan 5 turn terakhir per user
- **Konteks personal vs umum** — struk milik user disimpan terpisah, tidak bisa diakses user lain
- **Person query detection** — query tentang orang otomatis bypass ke web scrape + ringkasan LLM

---

## Struktur Project

```
chatbot-lab/
├── main.py                 # Entry point FastAPI
├── requirements.txt
├── .env                    # Secrets (tidak di-commit)
├── .env.example            # Template konfigurasi
├── .gitignore
├── docker-compose.yaml     # Waha Docker setup
└── app/
    ├── config.py           # Load semua env vars
    ├── models.py           # Pydantic request models
    ├── memory.py           # In-memory chat history per user
    ├── llm.py              # OpenRouter wrapper + prompt builder
    ├── ocr.py              # EasyOCR + LLM receipt parser
    ├── rag.py              # ChromaDB + embedding + hybrid search
    ├── scraper.py          # SerpAPI + web scraping
    ├── storage.py          # CSV per user + folder management
    ├── whatsapp.py         # Waha client (send, download media)
    └── routers/
        ├── chat.py         # POST /chat
        ├── receipts.py     # POST /upload-receipt, GET /receipts/{user_id}
        └── webhook.py      # POST /webhook/waha
```

---

## Tech Stack

| Komponen | Library/Service |
|---|---|
| Web Framework | FastAPI + Uvicorn |
| Vector Store | ChromaDB Cloud |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` |
| LLM | OpenRouter (fallback chain: Llama → Nemotron → Gemma → Phi → auto) |
| Web Search | SerpAPI (Google) |
| OCR | EasyOCR (`id`, `en`) |
| WhatsApp | Waha (Docker) |
| Storage | CSV per user + folder per user |

---

## Prasyarat

- Python 3.10+
- Docker (untuk Waha)
- Akun & API key dari:
  - [OpenRouter](https://openrouter.ai) — LLM
  - [ChromaDB Cloud](https://trychroma.com) — vector store
  - [SerpAPI](https://serpapi.com) — web search
  - [Waha](https://waha.devlike.pro) — WhatsApp gateway

---

## Instalasi

### 1. Clone & buat virtual environment

```bash
git clone <repo-url>
cd chatbot-lab
python3 -m venv venv
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Konfigurasi `.env`

Salin template dan isi dengan kredensial kamu:

```bash
cp .env.example .env
```

Edit `.env`:

```env
OPENROUTER_API_KEY=sk-or-v1-...
CHROMA_API_KEY=ck-...
CHROMA_TENANT=your-tenant-id
CHROMA_DATABASE=rag-lab
SERPAPI_API_KEY=your-serpapi-key
WAHA_API_KEY=your-waha-api-key
WAHA_URL=http://localhost:3000
WAHA_SESSION=default
```

### 4. Jalankan Waha (WhatsApp)

```bash
docker compose up -d
```

Buka Waha dashboard di `http://localhost:3000` → scan QR code untuk login WhatsApp.

Daftarkan webhook URL di Waha dashboard:
```
http://<IP-server>:8000/webhook/waha
```

> Gunakan [ngrok](https://ngrok.com) jika development di localhost:
> ```bash
> ngrok http 8000
> ```

### 5. Jalankan server

```bash
python3 main.py
```

Atau langsung via uvicorn:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

---

## API Endpoints

### `POST /chat`

Chat berbasis RAG dengan web search + konteks pribadi user.

**Request:**
```json
{
  "user_id": "628123456789",
  "query": "berapa harga beras sekarang?"
}
```

**Response:**
```json
{
  "query": "berapa harga beras sekarang?",
  "answer": "...",
  "model_used": "meta-llama/llama-3.3-70b-instruct:free",
  "context_count": 3,
  "context": [...]
}
```

---

### `POST /upload-receipt`

Upload foto struk belanja untuk di-OCR dan diparse.

**Request:** `multipart/form-data`
| Field | Type | Keterangan |
|---|---|---|
| `file` | file | Foto struk (jpg, png, webp) |
| `user_id` | string | ID user pemilik struk |

**Response:**
```json
{
  "status": "ok",
  "user_id": "628123456789",
  "struk": {
    "nama_toko": "Indomaret",
    "tanggal": "10/04/2026",
    "total": "Rp 45.000",
    "items": [...]
  },
  "raw_text": "..."
}
```

---

### `GET /receipts/{user_id}`

Lihat riwayat struk belanja milik user.

**Response:**
```json
{
  "user_id": "628123456789",
  "count": 5,
  "receipts": [...]
}
```

---

### `POST /webhook/waha`

Callback dari Waha. **Jangan dipanggil manual** — didaftarkan ke Waha sebagai webhook URL.

Mendukung:
- **Pesan teks** → RAG pipeline
- **Foto/gambar** → OCR struk → balas ringkasan

---

### `GET /health`

Health check.

```json
{ "status": "ok", "chroma_docs": 42 }
```

---

## Cara Kerja RAG

```
User kirim pesan
      │
      ▼
Person query? (siapa, profil, biodata, dll)
  ├── YA  → SerpAPI search → scrape artikel → LLM rangkum → balas
  └── TIDAK
        │
        ▼
  SerpAPI search → scrape → simpan ke ChromaDB (source=web, shared)
        │
        ▼
  ChromaDB query:
    - Struk pribadi user (source=receipt, user_id=X)
    - Web scrape relevan (source=web, semua user)
        │
        ▼
  Scoring cosine similarity (personal ×1.5 boost)
        │
        ▼
  Top 5 konteks → LLM → jawaban → balas user
```

---

## WhatsApp — Kirim Foto Struk

User cukup kirim foto struk/nota ke nomor WhatsApp bot. Sistem akan otomatis:
1. Download gambar dari Waha
2. Jalankan OCR (EasyOCR, support Indonesia & English)
3. Parse dengan LLM (detect currency, bahasa, item, total, dll)
4. Simpan ke `receipts/{user_id}/` (gambar) dan `receipts/{user_id}.csv`
5. Simpan teks ke ChromaDB untuk referensi percakapan berikutnya
6. Balas dengan ringkasan struk

---

## Penyimpanan Data

| Tipe | Lokasi | Akses |
|---|---|---|
| Gambar struk | `receipts/{user_id}/` | Per user |
| Riwayat struk | `receipts/{user_id}.csv` | Per user |
| Embedding struk | ChromaDB (`source=receipt, user_id=X`) | Per user |
| Pengetahuan web | ChromaDB (`source=web`) | Shared semua user |
| Chat history | In-memory (5 turn terakhir) | Per user, reset saat restart |


---

## Development

Setelah edit kode, server auto-reload karena `--reload` flag. Untuk cek logs:

```bash
# Lihat isi ChromaDB
curl http://localhost:8000/docs

# Health check
curl http://localhost:8000/health

# Test chat
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test123", "query": "harga bensin hari ini?"}'
```
