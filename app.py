from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml
from streamlit_autorefresh import st_autorefresh

from collector import collect_once, load_seed_file
from db import connect, init_db, latest_rows, load_seed
from scoring import choose

CONFIG_PATH = Path("config.yaml")


def money(value: int | float | None) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{int(value):,} ₽".replace(",", " ")


def load_config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def prepare_db() -> sqlite3.Connection:
    conn = connect()
    init_db(conn)
    load_seed(conn, load_seed_file())
    return conn


cfg = load_config()
auction_cfg = cfg["auction"]
strategy_cfg = cfg["strategy"]
hard_cap = int(auction_cfg["hard_cap_rub"])

st.set_page_config(page_title="Радар паркинга 31.1", layout="wide")
st.title("Радар паркинга 31.1 — Ильинские луга")
st.caption("Решение принимает человек. Радар только собирает данные и сравнивает альтернативы.")

with st.sidebar:
    st.header("Мониторинг")
    auto = st.toggle("Автообновление", value=False)
    poll_seconds = st.number_input(
        "Интервал, секунд",
        min_value=10,
        max_value=300,
        value=int(auction_cfg.get("poll_seconds", 15)),
        step=5,
    )
    if auto:
        st_autorefresh(interval=int(poll_seconds * 1000), key="auction-refresh")

    if st.button("Собрать данные сейчас", use_container_width=True):
        with st.spinner("Запрашиваю данные ПИК…"):
            result = collect_once()
        if result.get("ok"):
            st.success(result.get("message", "Готово"))
        else:
            st.warning(result.get("message", "Данные ПИК получить не удалось"))

    st.divider()
    st.metric("Жёсткий потолок", money(hard_cap))
    st.write(f"Шаг ставки: **{money(auction_cfg['bid_step_rub'])}**")
    st.write(f"Плата за лот: **{money(auction_cfg['participation_fee_rub'])}**")

# При включённом автообновлении одновременно делаем новый снимок.
if auto:
    collect_once()

conn = prepare_db()
rows = [dict(row) for row in latest_rows(conn)]

if not rows:
    st.error("В базе пока нет машиномест.")
    st.stop()

decision = choose(
    rows,
    hard_cap=hard_cap,
    premium_gap=int(auction_cfg["premium_preferred_gap_rub"]),
    cheap_gap=int(auction_cfg["cheap_preferred_gap_rub"]),
)

st.subheader("Что делать сейчас")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Рекомендация", decision.action)
col2.metric(
    "Лучший премиум",
    f"№{decision.premium_number}" if decision.premium_number else "—",
    money(decision.premium_price) if decision.premium_price else None,
)
col3.metric(
    "Самое дешёвое",
    f"№{decision.cheap_number}" if decision.cheap_number else "—",
    money(decision.cheap_price) if decision.cheap_price else None,
)
col4.metric("Цена комфорта", money(decision.comfort_gap))
st.info(decision.reason)

frame = pd.DataFrame(rows)
frame["Рост от старта"] = frame["current_price_rub"] - frame["start_price_rub"]
frame["До потолка"] = hard_cap - frame["current_price_rub"]
frame["Группа"] = frame["group_name"].map({"premium": "Премиум", "watch": "Наблюдение"}).fillna("Остальные")
frame["Цена"] = frame["current_price_rub"]
frame["Старт"] = frame["start_price_rub"]
frame["Площадь"] = frame["area_m2"]
frame["Уровень"] = frame["level"]
frame["Место"] = frame["number"]
frame["Артикул"] = frame["article_id"]
frame["Карточка ПИК"] = frame["url"]
frame["Комментарий"] = frame["notes"].fillna("")

st.subheader("Все известные лоты")
show = frame[
    [
        "Место",
        "Уровень",
        "Площадь",
        "Группа",
        "Старт",
        "Цена",
        "Рост от старта",
        "До потолка",
        "Комментарий",
        "Карточка ПИК",
        "Артикул",
    ]
].sort_values(["Цена", "Место"], na_position="last")

st.dataframe(
    show,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Старт": st.column_config.NumberColumn(format="%d ₽"),
        "Цена": st.column_config.NumberColumn(format="%d ₽"),
        "Рост от старта": st.column_config.NumberColumn(format="%d ₽"),
        "До потолка": st.column_config.NumberColumn(format="%d ₽"),
        "Площадь": st.column_config.NumberColumn(format="%.1f м²"),
        "Карточка ПИК": st.column_config.LinkColumn(display_text="Открыть"),
    },
)

st.subheader("Премиум против дешёвого")
premium_rows = frame[(frame["Группа"] == "Премиум") & (frame["Цена"] <= hard_cap)].sort_values("Цена")
cheap_rows = frame[(frame["Группа"] != "Премиум") & (frame["Цена"] <= hard_cap)].sort_values("Цена")

left, right = st.columns(2)
with left:
    st.markdown("**Премиум под потолком**")
    if premium_rows.empty:
        st.write("Нет вариантов.")
    else:
        st.dataframe(
            premium_rows[["Место", "Уровень", "Площадь", "Цена", "До потолка"]],
            hide_index=True,
            use_container_width=True,
        )
with right:
    st.markdown("**Самые дешёвые под потолком**")
    if cheap_rows.empty:
        st.write("Нет вариантов.")
    else:
        st.dataframe(
            cheap_rows[["Место", "Уровень", "Площадь", "Цена", "До потолка"]].head(10),
            hide_index=True,
            use_container_width=True,
        )

st.subheader("История выбранного лота")
options = [int(x) for x in frame["Место"].dropna().astype(int).tolist()]
selected_number = st.selectbox("Машиноместо", options=options, index=0)
selected = frame[frame["Место"] == selected_number].iloc[0]
history = pd.read_sql_query(
    """
    SELECT collected_at, current_price_rub, status, bid_count
    FROM snapshots
    WHERE article_id = ?
    ORDER BY collected_at
    """,
    conn,
    params=(int(selected["Артикул"]),),
)
if history.empty:
    st.write("Для этого лота пока нет автоматических снимков. Показана стартовая цена в таблице выше.")
else:
    history["collected_at"] = pd.to_datetime(history["collected_at"])
    st.line_chart(history.set_index("collected_at")["current_price_rub"], y_label="Цена, ₽")
    st.dataframe(history.tail(30), hide_index=True, use_container_width=True)
