"""Per-user receipt storage — images directory + CSV spreadsheet."""

import os
import csv
import time

from app.config import settings

os.makedirs(settings.receipts_dir, exist_ok=True)

_CSV_COLUMNS = [
    "timestamp", "user_id", "filename",
    "bahasa", "tanggal", "nama_toko",
    "subtotal", "pajak", "total", "dibayar", "kembalian",
    "model_used", "raw_text",
]


def user_dir(user_id: str) -> str:
    """Return (and create if needed) the image folder for a user."""
    path = os.path.join(settings.receipts_dir, user_id)
    os.makedirs(path, exist_ok=True)
    return path


def save_receipt_csv(user_id: str, filename: str, parsed: dict, raw_text: str) -> None:
    csv_path = os.path.join(settings.receipts_dir, f"{user_id}.csv")
    exists = os.path.isfile(csv_path)
    row = {
        "timestamp" : time.strftime("%Y-%m-%d %H:%M:%S"),
        "user_id"   : user_id,
        "filename"  : filename,
        "bahasa"    : parsed.get("bahasa"),
        "tanggal"   : parsed.get("tanggal"),
        "nama_toko" : parsed.get("nama_toko"),
        "subtotal"  : parsed.get("subtotal"),
        "pajak"     : parsed.get("pajak"),
        "total"     : parsed.get("total"),
        "dibayar"   : parsed.get("dibayar"),
        "kembalian" : parsed.get("kembalian"),
        "model_used": parsed.get("model_used"),
        "raw_text"  : raw_text,
    }
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_COLUMNS)
        if not exists:
            writer.writeheader()
        writer.writerow(row)
    print(f"[CSV] Saved → {csv_path}")


def read_receipts_csv(user_id: str) -> list[dict]:
    csv_path = os.path.join(settings.receipts_dir, f"{user_id}.csv")
    if not os.path.isfile(csv_path):
        return []
    with open(csv_path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))
