import os
import time
import shutil

from fastapi import APIRouter, UploadFile, File, Form

from app.ocr import read_image, parse_receipt
from app.rag import save_docs
from app.storage import user_dir, save_receipt_csv, read_receipts_csv

router = APIRouter()


@router.post("/upload-receipt")
def upload_receipt(file: UploadFile = File(...), user_id: str = Form(...)):
    dest_dir  = user_dir(user_id)
    file_path = os.path.join(dest_dir, f"{int(time.time())}_{file.filename}")

    with open(file_path, "wb") as buf:
        shutil.copyfileobj(file.file, buf)

    text   = read_image(file_path)
    parsed = parse_receipt(text)

    save_docs([text], meta={"user_id": user_id, "source": "receipt"})
    save_receipt_csv(user_id, file.filename, parsed, text)

    return {
        "status"  : "ok",
        "user_id" : user_id,
        "struk"   : parsed,
        "raw_text": text,
    }


@router.get("/receipts/{user_id}")
def get_receipts(user_id: str):
    rows = read_receipts_csv(user_id)
    return {"user_id": user_id, "count": len(rows), "receipts": rows}
