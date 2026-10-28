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
        return {k: short_shape(v, depth - 1) for k, v in list(value.items())[:40]}
    if isinstance(value, list):
        return {"type": "list", "len": len(value), "first": short_shape(value[0], depth - 1) if value else None}
    return type(value).__name__


def interesting_paths(value, prefix=""):
    found = []
    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else key
            lowered = key.lower()
            if any(word in lowered for word in ("auction", "bid", "price", "number", "status", "floor", "bulk", "section", "date", "start", "end")):
                if not isinstance(item, (dict, list)):
                    found.append((path, item))
            found.extend(interesting_paths(item, path))
    elif isinstance(value, list):
        for index, item in enumerate(value[:3]):
            found.extend(interesting_paths(item, f"{prefix}[{index}]"))
    return found


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
                print("top-level keys:", sorted(payload.keys()))
                for key in (
                    "id", "type_id", "status", "block_id", "bulk_id", "section_id", "floor",
                    "number", "number_stage", "name", "price", "area", "area_project", "url"
                ):
                    if key in payload:
                        print(f"{key}:", payload.get(key))
                print("interesting values:")
                for path, value in interesting_paths(payload)[:120]:
                    print(f"  {path} = {value}")
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
