"""Waha (WhatsApp HTTP API) client — send messages and download media."""

import requests

from app.config import settings

_HEADERS = {
    "X-Api-Key"   : settings.waha_api_key,
    "Content-Type": "application/json",
}


def send_text(chat_id: str, text: str) -> None:
    try:
        resp = requests.post(
            f"{settings.waha_url}/api/sendText",
            json={
                "session": settings.waha_session,
                "chatId" : chat_id,
                "text"   : text,
            },
            headers=_HEADERS,
            timeout=10,
        )
        if resp.status_code not in (200, 201):
            print(f"[WAHA] Send failed {chat_id}: {resp.status_code} {resp.text[:100]}")
        else:
            print(f"[WAHA] Sent to {chat_id}")
    except Exception as e:
        print(f"[WAHA] Exception: {e}")


def download_media(url: str) -> bytes | None:
    """Download media from a URL provided in the Waha webhook payload."""
    if url.startswith("/"):
        url = f"{settings.waha_url}{url}"
    try:
        resp = requests.get(url, headers={"X-Api-Key": settings.waha_api_key}, timeout=30)
        if resp.status_code == 200:
            return resp.content
        print(f"[WAHA MEDIA] Failed {url}: {resp.status_code} {resp.text[:100]}")
    except Exception as e:
        print(f"[WAHA MEDIA] Exception: {e}")
    return None


def extract_ids(msg: dict) -> tuple[str, str]:
    """
    Extract (chat_id, user_id) from a Waha message payload.
    chat_id  → used to reply back via WhatsApp
    user_id  → clean identifier used in all storage layers
    """
    chat_id = msg.get("chatId") or msg.get("from", "")
    user_id = (
        chat_id
        .replace("@c.us", "")
        .replace("@g.us", "")
        .replace("@lid", "")
        .strip()
    )
    return chat_id, user_id
