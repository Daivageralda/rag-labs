"""EasyOCR receipt reader + LLM-based parser with regex fallback."""

import re
import json
import logging

logging.getLogger("easyocr").setLevel(logging.ERROR)

import cv2
import easyocr

from app.llm import call_model, MODELS

_reader = easyocr.Reader(['id', 'en'])


# ──────────────────────────────────────────
# OCR
# ──────────────────────────────────────────

def read_image(image_path: str) -> str:
    img  = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return " ".join([r[1] for r in _reader.readtext(gray)])


# ──────────────────────────────────────────
# Helpers (private)
# ──────────────────────────────────────────

def _fmt_rp(raw: str) -> str:
    try:
        num = int(re.sub(r'[^\d]', '', raw))
        return f"Rp {num:,}".replace(",", ".")
    except Exception:
        return raw


def _regex_parse(text: str) -> dict:
    lower = text.lower()

    def extract(patterns):
        for pat in patterns:
            m = re.search(pat, lower)
            if m:
                return re.sub(r'[^\d]', '', m.group(1))
        return None

    total    = extract([r'total\s*(?:bayar)?\s*[:\-]?\s*([\d.,]+)',
                        r'grand\s*total\s*[:\-]?\s*([\d.,]+)',
                        r'jumlah\s*(?:bayar)?\s*[:\-]?\s*([\d.,]+)'])
    subtotal = extract([r'sub\s*total\s*[:\-]?\s*([\d.,]+)'])
    tax      = extract([r'pp[nh]\s*[:\-]?\s*([\d.,]+)',
                        r'tax\s*[:\-]?\s*([\d.,]+)',
                        r'pajak\s*[:\-]?\s*([\d.,]+)'])
    payment  = extract([r'tunai\s*[:\-]?\s*([\d.,]+)',
                        r'cash\s*[:\-]?\s*([\d.,]+)',
                        r'bayar\s*[:\-]?\s*([\d.,]+)'])
    change   = extract([r'kembali\s*[:\-]?\s*([\d.,]+)',
                        r'change\s*[:\-]?\s*([\d.,]+)'])
    date_m   = re.search(r'(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})', text)

    return {
        "bahasa"    : "unknown",
        "tanggal"   : date_m.group(1) if date_m else None,
        "nama_toko" : None,
        "items"     : [],
        "subtotal"  : _fmt_rp(subtotal) if subtotal else None,
        "pajak"     : _fmt_rp(tax)      if tax      else None,
        "total"     : _fmt_rp(total)    if total    else None,
        "dibayar"   : _fmt_rp(payment)  if payment  else None,
        "kembalian" : _fmt_rp(change)   if change   else None,
        "model_used": "regex",
    }


def _build_summary(parsed: dict) -> str:
    rows = []
    if parsed.get("nama_toko"): rows.append(f"  Store    : {parsed['nama_toko']}")
    if parsed.get("tanggal"):   rows.append(f"  Date     : {parsed['tanggal']}")
    items = parsed.get("items", [])
    if items:
        rows.append(f"  {'─'*26}")
        for it in items:
            rows.append(f"  {str(it.get('nama', '?'))[:20]:<20} {it.get('harga', '')}")
        rows.append(f"  {'─'*26}")
    for key, label in [
        ("subtotal", "Subtotal"), ("pajak", "Tax"),
        ("total", "Total"), ("dibayar", "Paid"), ("kembalian", "Change"),
    ]:
        if parsed.get(key):
            rows.append(f"  {label:<8} : {parsed[key]}")
    body = "\n".join(rows) if rows else "  (Not readable)"
    return f"\n{'='*30}\n RECEIPT SUMMARY\n{'='*30}\n{body}\n{'='*30}"


# ──────────────────────────────────────────
# Public
# ──────────────────────────────────────────

def parse_receipt(text: str) -> dict:
    """
    Parse receipt OCR text via LLM, fallback to regex.
    Handles any language/currency automatically.
    """
    prompt = f"""You are a precise receipt/invoice parser. Handle receipts in ANY language.
Return ONLY valid JSON — no explanation, no markdown.

{{
  "bahasa"   : "detected language (e.g. Indonesian / English / Japanese)",
  "tanggal"  : "DD/MM/YYYY or null",
  "nama_toko": "store name or null",
  "items"    : [{{"nama": "item", "qty": 1, "harga": "formatted price"}}],
  "subtotal" : "formatted price or null",
  "pajak"    : "tax/VAT/PPN amount or null",
  "total"    : "total amount or null",
  "dibayar"  : "amount paid or null",
  "kembalian": "change/kembalian or null"
}}

Currency rules:
- IDR → "Rp 10.000" (dot as thousand separator)
- USD → "$10.00", EUR → "€10.00", others → use symbol from receipt

OCR text:
{text}"""

    messages = [{"role": "user", "content": prompt}]

    for model in MODELS:
        result = call_model(model, messages, retries=2)
        if result is None:
            continue
        choices = result.get("choices", [])
        if not choices:
            continue
        content = choices[0].get("message", {}).get("content", "").strip()
        # strip markdown code fences if present
        content = re.sub(r'^```(?:json)?\s*', '', content, flags=re.MULTILINE)
        content = re.sub(r'\s*```$', '', content, flags=re.MULTILINE).strip()
        try:
            parsed = json.loads(content)
            parsed["model_used"] = result.get("model", model)
            parsed["ringkasan"]  = _build_summary(parsed)
            print(f"[OCR] Parsed with {parsed['model_used']}")
            return parsed
        except json.JSONDecodeError:
            continue

    print("[OCR] All models failed, falling back to regex")
    parsed = _regex_parse(text)
    parsed["ringkasan"] = _build_summary(parsed)
    return parsed
