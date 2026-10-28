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
PROJECT_NAME = os.getenv("PIK_PROJECT_NAME", "Ильинские луга")
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
    response = requests.get(f"{API_BASE}{path}", params=params, headers=HEADERS, timeout=30)
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


def article_from_item(item: dict[str, Any]) -> int | None:
    layout = item.get("layout")
    if isinstance(layout, dict):
        article = as_int(layout.get("name"))
        if article:
            return article
    return as_int(
        item.get("article_id")
        or item.get("article")
        or item.get("property_id")
        or item.get("flat_id")
        or item.get("id")
    )


def extract_filter_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if not isinstance(payload, dict):
        return []

    for key in ("results", "items", "flats", "properties", "objects"):
        value = payload.get(key)
        if isinstance(value, list):
            return [x for x in value if isinstance(x, dict)]

    data = payload.get("data")
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in ("results", "items", "flats", "properties", "objects"):
            value = data.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
    return []


def flatten_chessplan(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Разворачивает bulk → section → floor → flats в плоский список машиномест."""
    result: list[dict[str, Any]] = []
    for bulk in payload.get("bulks") or []:
        if not isinstance(bulk, dict):
            continue
        for section in bulk.get("sections") or []:
            if not isinstance(section, dict):
                continue
            floors = section.get("floors") or {}
            if isinstance(floors, list):
                floors = {str(index + 1): value for index, value in enumerate(floors)}
            if not isinstance(floors, dict):
                continue

            for floor_number, floor_data in floors.items():
                if not isinstance(floor_data, dict):
                    continue
                for item in floor_data.get("flats") or []:
                    if not isinstance(item, dict):
                        continue
                    row = dict(item)
                    row["_level"] = as_int(floor_number)
                    row["_bulk_name"] = bulk.get("name")
                    row["_section_name"] = section.get("name")
                    result.append(row)
    return result


def normalize_item(item: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    article_id = article_from_item(item)
    number = as_int(item.get("number") or item.get("parking_number") or item.get("property_number"))
    level = as_int(item.get("_level") or item.get("level") or item.get("floor") or item.get("floor_number"))
    area = as_float(item.get("area") or item.get("area_m2") or item.get("total_area"))
    price = as_int(
        item.get("auction_price")
        or item.get("current_price")
        or item.get("price")
        or item.get("min_price")
        or item.get("full_price")
    )
    status = item.get("status") or item.get("sale_status") or item.get("availability") or item.get("state")
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

    payload = get_json("/v2/filter", {"filter": 1})
    save_raw("filter-projects", payload)
    blocks = payload.get("block") if isinstance(payload, dict) else None
    if not isinstance(blocks, list):
        return None

    wanted = PROJECT_NAME.casefold().replace("ё", "е")
    candidates: list[tuple[int, str]] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        block_id = as_int(block.get("id"))
        name = str(block.get("name") or "").strip()
        normalized = name.casefold().replace("ё", "е")
        if block_id and wanted in normalized:
            candidates.append((block_id, name))

    if len(candidates) == 1:
        print(f"Найден ЖК: {candidates[0][1]} (block_id={candidates[0][0]})")
        return candidates[0][0]

    if candidates:
        # При нескольких совпадениях берём точное по имени, иначе первое и явно пишем это в лог.
        for block_id, name in candidates:
            if name.casefold().replace("ё", "е").startswith(wanted):
                print(f"Найден ЖК: {name} (block_id={block_id})")
                return block_id
        print(f"Найдено несколько ЖК: {candidates}; использую первый.")
        return candidates[0][0]
    return None


def fetch_parking(block_id: int) -> tuple[list[dict[str, Any]], Any | None]:
    chessplan = get_json("/v1/bulk/chessplan", {"new": 1, "block_id": block_id, "types": 5})
    save_raw("parking-chessplan", chessplan)
    items = flatten_chessplan(chessplan if isinstance(chessplan, dict) else {})

    # Новый filter API полезен тем, что, по свежему публичному парсеру,
    # в нём есть данные об аукционе. Пока сохраняем ответ целиком для изучения схемы.
    auction_payload = None
    try:
        auction_payload = get_json("/v2/filter", {"type": 5, "block": block_id})
        save_raw("parking-v2-filter", auction_payload)
    except Exception as exc:
        print(f"Не удалось получить v2/filter для паркинга: {exc}")

    return items, auction_payload


def collect_once() -> dict[str, Any]:
    conn = connect()
    init_db(conn)
    seed = load_seed_file()
    load_seed(conn, seed)

    try:
        block_id = resolve_block_id()
    except Exception as exc:
        return {
            "ok": False,
            "message": f"Не удалось получить список проектов ПИК: {exc}",
            "count": 0,
        }

    if not block_id:
        return {
            "ok": False,
            "message": f"Не удалось найти block_id проекта «{PROJECT_NAME}». Известные лоты загружены из seed_lots.csv.",
            "count": 0,
        }

    try:
        items, auction_payload = fetch_parking(block_id)
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
        else:
            # Для найденных через API лотов первая увиденная цена пока служит стартовой.
            lot["start_price_rub"] = snapshot.get("current_price_rub")

        upsert_lot(conn, lot)
        insert_snapshot(conn, snapshot)
        written += 1

    auction_items = len(extract_filter_items(auction_payload)) if auction_payload is not None else 0
    return {
        "ok": True,
        "message": f"Собрано машиномест: {written}",
        "count": written,
        "block_id": block_id,
        "auction_filter_items": auction_items,
    }


if __name__ == "__main__":
    result = collect_once()
    print(json.dumps(result, ensure_ascii=False, indent=2))
