from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable, Mapping, Any


@dataclass(frozen=True)
class ComparableMetrics:
    project: str
    weight: float
    parking_price_rub: float
    parking_price_m2_rub: float
    parking_price_in_apartment_m2: float | None
    parking_m2_to_apartment_ratio: float | None
    parking_m2_to_storage_ratio: float | None


def _num(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def recency_weight(event_date: str) -> float:
    """Основная модель сознательно использует только 2025–2026 годы."""
    year = int(str(event_date)[:4])
    if year >= 2026:
        return 1.0
    if year == 2025:
        return 0.75
    return 0.0


def comparable_weight(row: Mapping[str, Any]) -> float:
    """Прозрачный вес аналога без скрытой модели и ML.

    Все коэффициенты похожести хранятся в CSV и видны пользователю. Если поле
    не заполнено, аналог не получает за него бонус и используется нейтральное
    значение 1.0 только для технического расчёта.
    """
    factors = [
        recency_weight(str(row.get("event_date") or "1900-01-01")),
        _num(row.get("source_confidence")) or 1.0,
        _num(row.get("transport_similarity")) or 1.0,
        _num(row.get("parking_similarity")) or 1.0,
        _num(row.get("stage_similarity")) or 1.0,
    ]
    weight = 1.0
    for factor in factors:
        weight *= max(0.0, min(1.0, factor))
    return weight


def derive_metrics(row: Mapping[str, Any]) -> ComparableMetrics | None:
    price = _num(row.get("parking_price_rub"))
    area = _num(row.get("parking_area_m2"))
    apartment_m2 = _num(row.get("apartment_price_m2_rub"))
    storage_m2 = _num(row.get("storage_price_m2_rub"))
    if not price or not area or area <= 0:
        return None

    parking_m2 = price / area
    return ComparableMetrics(
        project=str(row.get("project") or ""),
        weight=comparable_weight(row),
        parking_price_rub=price,
        parking_price_m2_rub=parking_m2,
        parking_price_in_apartment_m2=(price / apartment_m2) if apartment_m2 else None,
        parking_m2_to_apartment_ratio=(parking_m2 / apartment_m2) if apartment_m2 else None,
        parking_m2_to_storage_ratio=(parking_m2 / storage_m2) if storage_m2 else None,
    )


def weighted_median(values: Iterable[tuple[float, float]]) -> float | None:
    prepared = sorted((value, weight) for value, weight in values if weight > 0)
    if not prepared:
        return None
    total = sum(weight for _, weight in prepared)
    threshold = total / 2
    running = 0.0
    for value, weight in prepared:
        running += weight
        if running >= threshold:
            return value
    return prepared[-1][0]


def estimate_from_comparables(
    rows: Iterable[Mapping[str, Any]],
    target_apartment_price_m2_rub: float,
    target_area_m2: float,
    target_storage_price_m2_rub: float | None = None,
) -> dict[str, float | None]:
    metrics = [metric for row in rows if (metric := derive_metrics(row)) and metric.weight > 0]

    by_total_multiple = weighted_median(
        (
            metric.parking_price_in_apartment_m2 * target_apartment_price_m2_rub,
            metric.weight,
        )
        for metric in metrics
        if metric.parking_price_in_apartment_m2 is not None
    )

    by_parking_m2 = weighted_median(
        (
            metric.parking_m2_to_apartment_ratio
            * target_apartment_price_m2_rub
            * target_area_m2,
            metric.weight,
        )
        for metric in metrics
        if metric.parking_m2_to_apartment_ratio is not None
    )

    by_storage = None
    if target_storage_price_m2_rub:
        by_storage = weighted_median(
            (
                metric.parking_m2_to_storage_ratio
                * target_storage_price_m2_rub
                * target_area_m2,
                metric.weight,
            )
            for metric in metrics
            if metric.parking_m2_to_storage_ratio is not None
        )

    estimates = [x for x in (by_total_multiple, by_parking_m2, by_storage) if x is not None]
    central = sorted(estimates)[len(estimates) // 2] if estimates else None

    return {
        "по_цене_квартирного_метра": by_total_multiple,
        "по_цене_метра_паркинга": by_parking_m2,
        "по_цене_кладовой": by_storage,
        "центральная_оценка": central,
        "число_аналогов": float(len(metrics)),
    }
