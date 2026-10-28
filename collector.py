from __future__ import annotations

import csv
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import requests

from db import connect, init_db, insert_snapshot, load_seed, upsert_lot

API_BASE = "https://api.pik.ru"
SEED_PATH = Path("data/seed_lots.csv")
RAW_DIR = Path("data/raw")
DEFAULT_WORKERS = int(os.getenv("PIK_WORKERS", "6"))
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/150 Safari/537.36",
    "Accept": "application/json,text/plain,*/*",
    "Referer": "https://www.pik.ru/",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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


def recursive_find(obj: Any, keys: tuple[str, ...]) -> Any:
    """Возвращает первое непустое значение любого из ключей во вложенном JSON."""
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


def save_raw(name: str, payload: Any) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    (RAW_DIR / f"{stamp}-{name}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def get_json(path: str, params: dict[str, Any] | None = None) -> Any:
    response = requests.get(
        f"{API_BASE}{path}", params=params, headers=HEADERS, timeout=15
    )
    response.raise_for_status()
    return response.json()


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


def fetch_article(article_id: int) -> dict[str, Any]:
    """Карточки машиномест ПИК доступны через тот же v2/flat endpoint."""
    payload = get_json("/v2/flat", {"id": article_id})
    if not isinstance(payload, dict):
        raise ValueError(f"Неожиданный ответ для артикула {article_id}")
    return payload


def current_price(payload: dict[str, Any]) -> int | None:
    """На карточке аукционного машиноместа поле price является текущей ценой."""
    return as_int(payload.get("price")) or as_int(
        recursive_find(
            payload,
            (
                "auction_price",
                "auctionPrice",
                "current_bid",
                "currentBid",
                "current_price",
                "currentPrice",
            ),
        )
    )


def normalize_article(
    payload: dict[str, Any], seed: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    article_id = as_int(payload.get("id")) or seed["article_id"]

    api_number = as_int(
        payload.get("number_stage")
        or payload.get("numberStage")
        or payload.get("apartmentNumber")
        or payload.get("number")
    )
    api_level = as_int(payload.get("floor") or payload.get("level"))
    api_area = as_float(
        payload.get("area") or payload.get("area_project") or payload.get("area_projected")
    )

    lot = dict(seed)
    lot.update(
        {
            "article_id": article_id,
            "number": api_number or seed.get("number"),
            "level": api_level or seed.get("level"),
            "area_m2": api_area or seed.get("area_m2"),
            "url": f"https://www.pik.ru/parking/{article_id}",
        }
    )

    snapshot = {
        "article_id": article_id,
        "collected_at": now_iso(),
        "current_price_rub": current_price(payload),
        "status": str(payload.get("status")) if payload.get("status") is not None else None,
        "auction_start": payload.get("startAuctionDate")
        or recursive_find(
            payload,
            (
                "auction_start",
                "auction_start_at",
                "auctionStart",
                "auctionStartAt",
                "auction_date_start",
            ),
        ),
        "auction_end": payload.get("endAuctionDate")
        or recursive_find(
            payload,
            (
                "auction_end",
                "auction_end_at",
                "auctionEnd",
                "auctionEndAt",
                "auction_date_end",
            ),
        ),
        "bid_count": as_int(payload.get("auctionBidsCount"))
        or as_int(
            recursive_find(payload, ("bid_count", "bids_count", "bidCount", "bidsCount"))
        )
        or 0,
        "raw_json": payload,
    }
    for key in ("auction_start", "auction_end"):
        if snapshot[key] is not None:
            snapshot[key] = str(snapshot[key])
    return lot, snapshot


def _fetch_one(seed: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    article_id = seed.get("article_id")
    if not article_id:
        raise ValueError("В seed_lots.csv найден лот без article_id")
    payload = fetch_article(int(article_id))
    if os.getenv("PIK_SAVE_RAW") == "1":
        save_raw(str(article_id), payload)
    return normalize_article(payload, seed)


def collect_once(
    article_ids: Iterable[int] | None = None, workers: int = DEFAULT_WORKERS
) -> dict[str, Any]:
    """Снимает один срез цен по выбранным или всем 70 аукционным лотам."""
    conn = connect()
    init_db(conn)
    seeds = load_seed_file()
    load_seed(conn, seeds)

    selected = set(int(x) for x in article_ids) if article_ids is not None else None
    seeds_to_fetch = [
        seed
        for seed in seeds
        if seed.get("article_id") and (selected is None or seed["article_id"] in selected)
    ]

    written = 0
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        future_to_seed = {pool.submit(_fetch_one, seed): seed for seed in seeds_to_fetch}
        for future in as_completed(future_to_seed):
            seed = future_to_seed[future]
            try:
                lot, snapshot = future.result()
                upsert_lot(conn, lot)
                insert_snapshot(conn, snapshot)
                written += 1
            except Exception as exc:
                errors.append(f"{seed.get('article_id')}: {exc}")

    return {
        "ok": written > 0 and not errors,
        "message": f"Получено {written} из {len(seeds_to_fetch)} лотов",
        "count": written,
        "requested": len(seeds_to_fetch),
        "errors": errors[:10],
    }


if __name__ == "__main__":
    print(json.dumps(collect_once(), ensure_ascii=False, indent=2))
