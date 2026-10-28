from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class Decision:
    action: str
    premium_number: int | None
    premium_price: int | None
    cheap_number: int | None
    cheap_price: int | None
    comfort_gap: int | None
    reason: str


UNAVAILABLE_STATUSES = {"sold", "unavailable", "booked", "reserved"}


def entry_price(row: Mapping[str, Any], bid_step: int) -> int:
    """Цена, которую нужно поставить прямо сейчас, чтобы войти в лот.

    До первой ставки стартовая цена сама является ценой входа. После появления
    хотя бы одной ставки нужно перебить текущую цену на один шаг.
    """
    price = int(row.get("current_price_rub") or row.get("start_price_rub") or 0)
    bid_count = int(row.get("bid_count") or 0)
    return price + bid_step if price > 0 and bid_count > 0 else price


def choose(
    rows: Iterable[Mapping[str, Any]],
    hard_cap: int,
    premium_gap: int,
    cheap_gap: int,
    bid_step: int = 20_000,
) -> Decision:
    prepared = []
    for row in rows:
        status = str(row.get("status") or "").lower()
        if status in UNAVAILABLE_STATUSES:
            continue
        price = entry_price(row, bid_step)
        if price <= 0:
            continue
        prepared.append((row, price))

    under_cap = [(row, price) for row, price in prepared if price <= hard_cap]
    if not under_cap:
        return Decision(
            "ВЫЙТИ",
            None,
            None,
            None,
            None,
            None,
            "Для входа во все доступные лоты уже нужна ставка выше жёсткого потолка.",
        )

    premiums = [
        (row, price)
        for row, price in under_cap
        if row.get("group_name") == "premium"
    ]
    non_premiums = [
        (row, price)
        for row, price in under_cap
        if row.get("group_name") != "premium"
    ]

    best_premium = min(premiums, key=lambda item: item[1], default=None)
    best_cheap = min(non_premiums, key=lambda item: item[1], default=None)

    if best_premium and not best_cheap:
        row, price = best_premium
        return Decision(
            "ПРЕМИУМ",
            row.get("number"),
            price,
            None,
            None,
            None,
            "Под потолком остались только премиальные варианты.",
        )

    if best_cheap and not best_premium:
        row, price = best_cheap
        return Decision(
            "ДЕШЁВОЕ",
            None,
            None,
            row.get("number"),
            price,
            None,
            "Премиальные варианты уже требуют ставки выше потолка.",
        )

    if not best_premium or not best_cheap:
        row, price = min(under_cap, key=lambda item: item[1])
        return Decision(
            "ЖДАТЬ",
            None,
            None,
            row.get("number"),
            price,
            None,
            "Недостаточно данных для сравнения групп.",
        )

    premium_row, premium_price = best_premium
    cheap_row, cheap_price = best_cheap
    gap = premium_price - cheap_price

    if gap <= premium_gap:
        return Decision(
            "ПРЕМИУМ",
            premium_row.get("number"),
            premium_price,
            cheap_row.get("number"),
            cheap_price,
            gap,
            f"Доплата за комфорт {gap:,} ₽ — в пределах заданной разумной премии.".replace(
                ",", " "
            ),
        )

    if gap >= cheap_gap:
        return Decision(
            "ДЕШЁВОЕ",
            premium_row.get("number"),
            premium_price,
            cheap_row.get("number"),
            cheap_price,
            gap,
            f"Доплата за премиум {gap:,} ₽ слишком велика; дешёвый вариант сохраняет капитал.".replace(
                ",", " "
            ),
        )

    return Decision(
        "ЖДАТЬ",
        premium_row.get("number"),
        premium_price,
        cheap_row.get("number"),
        cheap_price,
        gap,
        f"Разница {gap:,} ₽ находится в серой зоне; полезнее наблюдать за динамикой торгов.".replace(
            ",", " "
        ),
    )
