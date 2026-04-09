"""Web search (SerpAPI) + article scraping."""

import re
import json
import http.client
import requests
from bs4 import BeautifulSoup
import serpapi
# import http.client  # was used for serper.dev

from app.config import settings

_SCRAPE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}

_BLOCKED_DOMAINS = [
    "youtube.com", "facebook.com", "instagram.com",
    "twitter.com", "x.com", "linkedin.com", "reddit.com",
    "amazon.com", "loudboyz", "fictish", "wordhippo",
]


def _is_blocked(url: str) -> bool:
    return any(d in url for d in _BLOCKED_DOMAINS)


def _is_valid(text: str) -> bool:
    if not text or len(text) < 100:
        return False
    garbage = [
        "varnish cache server", "not allowed", "access denied",
        "403 forbidden", "enable javascript", "please verify you are a human",
        "cloudflare", "sign in to continue",
    ]
    return not any(g in text.lower() for g in garbage)


def scrape_article(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        return ""
    if _is_blocked(url):
        return ""
    try:
        resp = requests.get(url, timeout=7, headers=_SCRAPE_HEADERS)
        if resp.status_code != 200:
            return ""
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        block = soup.find("article") or soup.find("main")
        text = (
            block.get_text(separator=" ", strip=True)
            if block
            else " ".join(p.get_text(strip=True) for p in soup.find_all("p"))
        )
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:3000] if _is_valid(text) else ""
    except Exception as e:
        print(f"[SCRAPE ERROR] {url}: {e}")
        return ""


def search_and_scrape(query: str) -> list[str]:
    """Search SerpAPI and scrape up to 3 articles. Returns list of text."""
    try:
        results = serpapi.search(
            engine="google",
            q=query,
            api_key=settings.serpapi_api_key,
            num=5,
            hl="id",
        )
        links = [
            r["link"]
            for r in results.get("organic_results", [])
            if r.get("link") and not _is_blocked(r["link"])
        ][:4]
    except Exception as e:
        print(f"[SERPAPI ERROR]: {e}")
        return []

    # --- serper.dev (commented out) ---
    # conn = http.client.HTTPSConnection("google.serper.dev")
    # payload = json.dumps({"q": query, "num": 5, "hl": "id"})
    # conn.request("POST", "/search", payload,
    #     {"X-API-KEY": settings.serper_api_key, "Content-Type": "application/json"})
    # data = json.loads(conn.getresponse().read().decode("utf-8"))
    # links = [r["link"] for r in data.get("organic", []) if r.get("link") and not _is_blocked(r["link"])][:4]
    # -----------------------------------

    docs = []
    for url in links:
        text = scrape_article(url)
        if text:
            docs.append(text)
        if len(docs) >= 3:
            break
    return docs
