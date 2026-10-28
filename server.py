from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock
from typing import Any

import yaml
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from collector import fetch_article, load_seed_file, normalize_article
from scoring import choose, entry_price

BASE_DIR = Path(__file__).parent
PWA_DIR = BASE_DIR / "pwa"
CONFIG = yaml.safe_load((BASE_DIR / "config.yaml").read_text(encoding="utf-8"))
AUCTION = CONFIG["auction"]
HARD_CAP = int(AUCTION["hard_cap_rub"])
BID_STEP = int(AUCTION["bid_step_rub"])
CACHE_TTL = 8

app = FastAPI(title="Радар паркинга 31.1")
_cache: dict[str, Any] = {"ts": 0.0, "payload": None}
_cache_lock = Lock()


def _fetch_live_row(seed: dict[str, Any]) -> dict[str, Any]:
    payload = fetch_article(int(seed["article_id"]))
    lot, snapshot = normalize_article(payload, seed)
    row = {
        **lot,
        "group_name": lot.get("group"),
        "current_price_rub": snapshot.get("current_price_rub"),
        "status": snapshot.get("status"),
        "auction_start": snapshot.get("auction_start"),
        "auction_end": snapshot.get("auction_end"),
        "bid_count": int(snapshot.get("bid_count") or 0),
    }
    row["entry_price_rub"] = entry_price(row, BID_STEP)
    row["under_cap"] = bool(row["entry_price_rub"] and row["entry_price_rub"] <= HARD_CAP)
    return row


def _collect_live() -> dict[str, Any]:
    seeds = load_seed_file()
    rows: list[dict[str, Any]] = []
    errors: list[str] = []

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(_fetch_live_row, seed): seed for seed in seeds}
        for future in as_completed(futures):
            seed = futures[future]
            try:
                rows.append(future.result())
            except Exception as exc:
                errors.append(f"{seed.get('article_id')}: {exc}")

    rows.sort(key=lambda row: (row.get("entry_price_rub") or 10**12, row.get("number") or 10**9))
    decision = choose(
        rows,
        hard_cap=HARD_CAP,
        premium_gap=int(AUCTION["premium_preferred_gap_rub"]),
        cheap_gap=int(AUCTION["cheap_preferred_gap_rub"]),
        bid_step=BID_STEP,
    )

    return {
        "ok": bool(rows),
        "updated_at": int(time.time()),
        "hard_cap_rub": HARD_CAP,
        "bid_step_rub": BID_STEP,
        "participation_fee_rub": int(AUCTION["participation_fee_rub"]),
        "poll_seconds": int(AUCTION.get("poll_seconds", 30)),
        "decision": {
            "action": decision.action,
            "premium_number": decision.premium_number,
            "premium_price": decision.premium_price,
            "cheap_number": decision.cheap_number,
            "cheap_price": decision.cheap_price,
            "comfort_gap": decision.comfort_gap,
            "reason": decision.reason,
        },
        "lots": rows,
        "errors": errors,
    }


def get_live_payload(force: bool = False) -> dict[str, Any]:
    now = time.time()
    with _cache_lock:
        if not force and _cache["payload"] and now - _cache["ts"] < CACHE_TTL:
            return _cache["payload"]

    payload = _collect_live()
    with _cache_lock:
        _cache["ts"] = time.time()
        _cache["payload"] = payload
    return payload


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/lots")
def lots(force: bool = False) -> dict[str, Any]:
    return get_live_payload(force=force)


@app.get("/manifest.webmanifest")
def manifest() -> FileResponse:
    return FileResponse(PWA_DIR / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/sw.js")
def service_worker() -> FileResponse:
    return FileResponse(PWA_DIR / "sw.js", media_type="application/javascript")


@app.get("/icon.svg")
def icon() -> FileResponse:
    return FileResponse(PWA_DIR / "icon.svg", media_type="image/svg+xml")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(PWA_DIR / "index.html")


app.mount("/static", StaticFiles(directory=PWA_DIR), name="static")
