import os
import time

from fastapi import APIRouter, Request

from app.whatsapp import extract_ids, send_text, download_media
from app.memory import get_memory, update_memory
from app.scraper import search_and_scrape
from app.rag import build_context, save_docs, chunk_text
from app.ocr import read_image, parse_receipt
from app.storage import user_dir, save_receipt_csv
from app.llm import generate_answer, is_person_query

router = APIRouter()


@router.post("/webhook/waha")
async def waha_webhook(req: Request):
    data  = await req.json()
    event = data.get("event", "")

    if event != "message":
        return {"status": "ignored", "event": event}

    msg = data.get("payload", {})
    if msg.get("fromMe", False):
        return {"status": "ignored", "reason": "own message"}

    chat_id, user_id = extract_ids(msg)
    if not chat_id:
        return {"status": "ignored", "reason": "no chat_id"}

    has_media = msg.get("hasMedia", False)
    body      = (msg.get("body") or "").strip()

    print(f"[WEBHOOK] {chat_id} (uid={user_id}) | media={has_media} | body={body[:60]}")

    # ── Image / media ──
    if has_media:
        answer = _handle_image(msg, user_id)
        update_memory(user_id, "[image]", answer)
        send_text(chat_id, answer)
        return {"status": "ok", "type": "image", "user_id": user_id}

    # ── Text message ──
    if not body:
        return {"status": "ignored", "reason": "empty body"}

    history  = get_memory(user_id)
    external = search_and_scrape(body)

    # Query umum → simpan sebagai referensi bersama semua user (tanpa user_id)
    # Query orang → tidak disimpan sama sekali
    if not is_person_query(body):
        chunks = []
        for doc in external:
            chunks.extend(chunk_text(doc))
        save_docs(chunks, meta={"source": "web"})

    docs   = build_context(body, user_id, external)
    result = generate_answer(body, docs, history)
    answer = result["answer"]

    update_memory(user_id, body, answer)
    send_text(chat_id, answer)

    return {"status": "ok", "type": "text", "user_id": user_id}


def _handle_image(msg: dict, user_id: str) -> str:
    """Download image from Waha → OCR → parse receipt → save → return summary."""
    media     = msg.get("media") or {}
    mime      = media.get("mimetype", "")
    media_url = media.get("url") or ""

    print(f"[WEBHOOK IMG] media={media}")

    if not mime.startswith("image/"):
        return "⚠️ File yang dikirim bukan gambar. Kirim foto struk/nota ya."

    if not media_url:
        return "⚠️ URL media tidak tersedia di payload."

    ext      = mime.split("/")[-1].replace("jpeg", "jpg")
    filename = f"{int(time.time())}.{ext}"
    dest     = os.path.join(user_dir(user_id), filename)

    img_bytes = download_media(media_url)
    if not img_bytes:
        return "⚠️ Gagal mengunduh gambar. Coba kirim ulang."

    with open(dest, "wb") as f:
        f.write(img_bytes)

    text   = read_image(dest)
    parsed = parse_receipt(text)

    save_docs([text], meta={"user_id": user_id, "source": "receipt"})
    save_receipt_csv(user_id, filename, parsed, text)

    # Format reply for WhatsApp
    lines = ["🧾 *STRUK TERDETEKSI*"]
    if parsed.get("nama_toko"): lines.append(f"🏪 {parsed['nama_toko']}")
    if parsed.get("tanggal"):   lines.append(f"📅 {parsed['tanggal']}")

    items = parsed.get("items", [])
    if items:
        lines.append("─" * 20)
        for it in items:
            lines.append(f"• {it.get('nama', '')} — {it.get('harga', '')}")

    lines.append("─" * 20)
    if parsed.get("subtotal"):  lines.append(f"Subtotal  : {parsed['subtotal']}")
    if parsed.get("pajak"):     lines.append(f"Pajak     : {parsed['pajak']}")
    if parsed.get("total"):     lines.append(f"*Total    : {parsed['total']}*")
    if parsed.get("dibayar"):   lines.append(f"Dibayar   : {parsed['dibayar']}")
    if parsed.get("kembalian"): lines.append(f"Kembalian : {parsed['kembalian']}")

    if len(lines) <= 2:
        lines.append("(Struk tidak terbaca, coba foto lebih jelas)")

    return "\n".join(lines)
