from __future__ import annotations

import json

import requests

ARTICLE = 1070586
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/150 Safari/537.36",
    "Accept": "application/json,text/plain,*/*",
    "Referer": "https://www.pik.ru/",
}


def short_shape(value, depth=2):
    if depth < 0:
        return type(value).__name__
    if isinstance(value, dict):
        return {k: short_shape(v, depth - 1) for k, v in list(value.items())[:25]}
    if isinstance(value, list):
        return {"type": "list", "len": len(value), "first": short_shape(value[0], depth - 1) if value else None}
    return type(value).__name__


def probe(name: str, url: str):
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        print(f"\n=== {name} ===")
        print("status:", response.status_code)
        print("url:", response.url)
        print("content-type:", response.headers.get("content-type"))
        print("length:", len(response.content))
        if "json" in (response.headers.get("content-type") or ""):
            payload = response.json()
            print("shape:", json.dumps(short_shape(payload, 2), ensure_ascii=False))
            if isinstance(payload, dict):
                print("block_id:", payload.get("block_id") or payload.get("blockId"))
                print("id:", payload.get("id"))
                print("type:", payload.get("type"))
        else:
            text = response.text
            print("contains article:", str(ARTICLE) in text)
            for needle in ("__NEXT_DATA__", "block_id", "auction", "parking"):
                print(f"contains {needle}:", needle in text)
    except Exception as exc:
        print(f"\n=== {name} ===")
        print("error:", repr(exc))


if __name__ == "__main__":
    base = "https://api.pik.ru"
    probe("v1 flat query", f"{base}/v1/flat?id={ARTICLE}&similar=1")
    probe("v2 flat query", f"{base}/v2/flat?id={ARTICLE}")
    probe("v1 parking query", f"{base}/v1/parking?id={ARTICLE}")
    probe("v2 parking query", f"{base}/v2/parking?id={ARTICLE}")
    probe("карточка сайта", f"https://www.pik.ru/parking/{ARTICLE}")
