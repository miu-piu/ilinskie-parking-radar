from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml
from streamlit_autorefresh import st_autorefresh

from collector import collect_once, load_seed_file
from db import connect, init_db, latest_rows, load_seed
from scoring import choose, entry_price

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
hard_cap = int(auction_cfg["hard_cap_rub"])
bid_step = int(auction_cfg["bid_step_rub"])

st.set_page_config(page_title="Радар паркинга 31.1", layout="wide")
st.title("Радар паркинга 31.1 — Ильинские луга")
st.caption(
    "Радар ничего не покупает и не делает ставки. Он только следит за ПИК и сравнивает варианты."
)

with st.sidebar:
    st.header("Мониторинг")
    auto = st.toggle("Автообновление", value=False)
    poll_seconds = st.number_input(
        "Интервал полного опроса, секунд",
        min_value=10,
        max_value=300,
        value=int(auction_cfg.get("poll_seconds", 30)),
        step=5,
    )
    if poll_seconds < 20:
        st.caption("Частый опрос 70 карточек сильнее нагружает API ПИК. На старте лучше 30 секунд.")
    if auto:
        st_autorefresh(interval=int(poll_seconds * 1000), key="auction-refresh")

    if st.button("Собрать все 70 лотов сейчас", use_container_width=True):
        with st.spinner("Запрашиваю 70 карточек ПИК…"):
            result = collect_once()
        if result.get("ok"):
            st.success(result.get("message", "Готово"))
        else:
            st.warning(result.get("message", "Часть данных получить не удалось"))
            if result.get("errors"):
                st.code("\n".join(result["errors"]))

    st.divider()
    st.metric("Жёсткий потолок", money(hard_cap))
    st.write(f"Шаг ставки: **{money(bid_step)}**")
    st.write(f"Плата за вход в лот: **{money(auction_cfg['participation_fee_rub'])}**")

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
    bid_step=bid_step,
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
    "Самый дешёвый вход",
    f"№{decision.cheap_number}" if decision.cheap_number else "—",
    money(decision.cheap_price) if decision.cheap_price else None,
)
col4.metric("Цена комфорта", money(decision.comfort_gap))
st.info(decision.reason)

frame = pd.DataFrame(rows)
frame["Ставок"] = frame["bid_count"].fillna(0).astype(int)
frame["Цена сейчас"] = frame["current_price_rub"].fillna(frame["start_price_rub"])
frame["Цена входа"] = frame.apply(
    lambda row: entry_price(row.to_dict(), bid_step), axis=1
)
frame["Рост от старта"] = frame["Цена сейчас"] - frame["start_price_rub"]
frame["До потолка"] = hard_cap - frame["Цена входа"]
frame["Группа"] = (
    frame["group_name"]
    .map({"premium": "Премиум", "watch": "Наблюдение", "auction": "Аукцион"})
    .fillna("Аукцион")
)
frame["Старт"] = frame["start_price_rub"]
frame["Площадь"] = frame["area_m2"]
frame["Уровень"] = frame["level"]
frame["Место"] = frame["number"]
frame["Артикул"] = frame["article_id"]
frame["Карточка ПИК"] = frame["url"]
frame["Комментарий"] = frame["notes"].fillna("")
frame["Статус"] = frame["status"].fillna("—")
frame["Конец торгов"] = frame["auction_end"].fillna("—")
frame["Снимок"] = frame["collected_at"].fillna("—")

st.subheader("Все 70 лотов первого аукциона")
show = frame[
    [
        "Место",
        "Уровень",
        "Площадь",
        "Группа",
        "Старт",
        "Цена сейчас",
        "Ставок",
        "Цена входа",
        "Рост от старта",
        "До потолка",
        "Статус",
        "Конец торгов",
        "Комментарий",
        "Карточка ПИК",
        "Артикул",
    ]
].sort_values(["Цена входа", "Место"], na_position="last")

st.dataframe(
    show,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Старт": st.column_config.NumberColumn(format="%d ₽"),
        "Цена сейчас": st.column_config.NumberColumn(format="%d ₽"),
        "Цена входа": st.column_config.NumberColumn(format="%d ₽"),
        "Рост от старта": st.column_config.NumberColumn(format="%d ₽"),
        "До потолка": st.column_config.NumberColumn(format="%d ₽"),
        "Площадь": st.column_config.NumberColumn(format="%.1f м²"),
        "Карточка ПИК": st.column_config.LinkColumn(display_text="Открыть"),
    },
)

st.subheader("Премиум против дешёвого")
premium_rows = frame[
    (frame["Группа"] == "Премиум") & (frame["Цена входа"] <= hard_cap)
].sort_values("Цена входа")
cheap_rows = frame[
    (frame["Группа"] != "Премиум") & (frame["Цена входа"] <= hard_cap)
].sort_values("Цена входа")

left, right = st.columns(2)
with left:
    st.markdown("**Премиум под потолком**")
    if premium_rows.empty:
        st.write("Нет вариантов.")
    else:
        st.dataframe(
            premium_rows[
                ["Место", "Уровень", "Площадь", "Цена сейчас", "Ставок", "Цена входа", "До потолка"]
            ],
            hide_index=True,
            use_container_width=True,
        )
with right:
    st.markdown("**Самые дешёвые входы под потолком**")
    if cheap_rows.empty:
        st.write("Нет вариантов.")
    else:
        st.dataframe(
            cheap_rows[
                ["Место", "Уровень", "Площадь", "Цена сейчас", "Ставок", "Цена входа", "До потолка"]
            ].head(15),
            hide_index=True,
            use_container_width=True,
        )

st.subheader("История выбранного лота")
options = sorted({int(x) for x in frame["Место"].dropna().astype(int).tolist()})
if not options:
    st.write("Сначала нажмите «Собрать все 70 лотов сейчас», чтобы получить номера мест из API ПИК.")
else:
    selected_number = st.selectbox("Машиноместо", options=options, index=0)
    selected = frame[frame["Место"] == selected_number].iloc[0]
    history = pd.read_sql_query(
        """
        SELECT collected_at, current_price_rub, status, bid_count, auction_end
        FROM snapshots
        WHERE article_id = ?
        ORDER BY collected_at
        """,
        conn,
        params=(int(selected["Артикул"]),),
    )
    if history.empty:
        st.write("Для этого лота пока нет автоматических снимков.")
    else:
        history["collected_at"] = pd.to_datetime(history["collected_at"])
        st.line_chart(
            history.set_index("collected_at")["current_price_rub"],
            y_label="Цена, ₽",
        )
        st.dataframe(history.tail(50), hide_index=True, use_container_width=True)
