from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from db import connect, init_db, insert_snapshot, load_seed, upsert_lot

API_BASE = "https://api.pik.ru"
SAMPLE_LOT_ID = int(os.getenv("PIK_SAMPLE_LOT_ID", "1070586"))
SEED_PATH = Path("data/seed_lots.csv")
RAW_DIR = Path("data/raw")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/150 Safari/537.36",
    "Accept": "application/json,text/plain,*/*",
    "Referer": "https://www.pik.ru/",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def save_raw(name: str, payload: Any) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = RAW_DIR / f"{stamp}-{name}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def get_json(path: str, params: dict[str, Any] | None = None) -> Any:
    response = requests.get(f"{API_BASE}{path}", params=params, headers=HEADERS, timeout=20)
    response.raise_for_status()
    return response.json()


def recursive_find(obj: Any, keys: tuple[str, ...]) -> Any:
    if isinstance(obj, dict):
        for key in keys:
            if key in obj and obj[key] not in (None, ""):
                return obj[key]
        for value in obj.values():
            found = recursive_find(value, keys)
            if found not in (None, ""):
                return found
    elif isinstance(obj, list):
        for value in obj:
            found = recursive_find(value, keys)
            if found not in (None, ""):
                return found
    return None


def extract_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []

    for key in ("results", "items", "flats", "properties", "objects"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]

    data = payload.get("data")
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        for key in ("results", "items", "flats", "properties", "objects"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def as_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return int(value)
    try:
        return int(float(str(value).replace(" ", "").replace(",", ".")))
    except (TypeError, ValueError):
        return None


def as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(" ", "").replace(",", "."))
    except (TypeError, ValueError):
        return None


def normalize_item(item: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    article_id = as_int(recursive_find(item, ("id", "flat_id", "property_id", "article_id", "article")))
    number = as_int(recursive_find(item, ("number", "flat_number", "parking_number", "property_number")))
    level = as_int(recursive_find(item, ("level", "floor", "floor_number")))
    area = as_float(recursive_find(item, ("area", "area_m2", "total_area")))
    price = as_int(recursive_find(item, ("current_price", "price", "auction_price", "min_price", "full_price")))
    status = recursive_find(item, ("status", "sale_status", "availability", "state"))
    auction_start = recursive_find(item, ("auction_start", "auction_start_at", "auctionStart", "auction_date_start"))
    auction_end = recursive_find(item, ("auction_end", "auction_end_at", "auctionEnd", "auction_date_end"))
    bid_count = as_int(recursive_find(item, ("bid_count", "bids_count", "auction_bid_count")))

    lot = {
        "article_id": article_id,
        "number": number,
        "level": level,
        "area_m2": area,
        "start_price_rub": None,
        "group": None,
        "notes": None,
        "url": f"https://www.pik.ru/parking/{article_id}" if article_id else None,
    }
    snapshot = {
        "article_id": article_id,
        "collected_at": now_iso(),
        "current_price_rub": price,
        "status": str(status) if status is not None else None,
        "auction_start": str(auction_start) if auction_start is not None else None,
        "auction_end": str(auction_end) if auction_end is not None else None,
        "bid_count": bid_count,
        "raw_json": item,
    }
    return lot, snapshot


def load_seed_file() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with SEED_PATH.open("r", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            rows.append(
                {
                    "number": as_int(row.get("number")),
                    "article_id": as_int(row.get("article_id")),
                    "level": as_int(row.get("level")),
                    "area_m2": as_float(row.get("area_m2")),
                    "start_price_rub": as_int(row.get("start_price_rub")),
                    "group": row.get("group") or None,
                    "notes": row.get("notes") or None,
                    "url": row.get("url") or None,
                }
            )
    return rows


def resolve_block_id() -> int | None:
    from_env = as_int(os.getenv("PIK_BLOCK_ID"))
    if from_env:
        return from_env

    attempts = [f"/v1/flat/{SAMPLE_LOT_ID}", f"/v2/flat/{SAMPLE_LOT_ID}"]
    for path in attempts:
        try:
            payload = get_json(path)
            save_raw("sample-lot", payload)
            block_id = as_int(recursive_find(payload, ("block_id", "blockId")))
            if block_id:
                return block_id
        except Exception as exc:
            print(f"Не удалось получить {path}: {exc}")
    return None


def fetch_parking(block_id: int) -> list[dict[str, Any]]:
    all_items: list[dict[str, Any]] = []
    seen_ids: set[int] = set()

    # Основной вариант по аналогии с публичными парсерами ПИК.
    for page in range(1, 50):
        payload = get_json("/v2/flat", {"block_id": block_id, "types": 5, "page": page})
        if page == 1:
            save_raw("parking-v2-page-1", payload)
        items = extract_items(payload)
        if not items:
            break

        added = 0
        for item in items:
            item_id = as_int(recursive_find(item, ("id", "flat_id", "property_id", "article_id")))
            if item_id and item_id in seen_ids:
                continue
            if item_id:
                seen_ids.add(item_id)
            all_items.append(item)
            added += 1

        if added == 0 or len(items) < 50:
            break

    if all_items:
        return all_items

    # Запасной вариант: старый chessplan.
    payload = get_json("/v1/bulk/chessplan", {"new": 1, "block_id": block_id, "types": 5})
    save_raw("parking-chessplan", payload)
    return extract_items(payload)


def collect_once() -> dict[str, Any]:
    conn = connect()
    init_db(conn)
    seed = load_seed_file()
    load_seed(conn, seed)

    block_id = resolve_block_id()
    if not block_id:
        return {
            "ok": False,
            "message": "Не удалось автоматически определить block_id. Известные лоты загружены из seed_lots.csv.",
            "count": 0,
        }

    try:
        items = fetch_parking(block_id)
    except Exception as exc:
        return {
            "ok": False,
            "message": f"API ПИК недоступен или изменил формат: {exc}",
            "count": 0,
            "block_id": block_id,
        }

    written = 0
    seed_by_id = {row["article_id"]: row for row in seed if row.get("article_id")}
    for item in items:
        lot, snapshot = normalize_item(item)
        article_id = lot.get("article_id")
        if not article_id:
            continue

        # Не затираем вручную проверенные номер, старт и группу пустыми значениями API.
        if article_id in seed_by_id:
            merged = dict(seed_by_id[article_id])
            for key, value in lot.items():
                if value is not None:
                    merged[key] = value
            lot = merged

        upsert_lot(conn, lot)
        insert_snapshot(conn, snapshot)
        written += 1

    return {
        "ok": True,
        "message": f"Собрано объектов: {written}",
        "count": written,
        "block_id": block_id,
    }


if __name__ == "__main__":
    result = collect_once()
    print(json.dumps(result, ensure_ascii=False, indent=2))
