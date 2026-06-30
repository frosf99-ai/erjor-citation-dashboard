from __future__ import annotations

import datetime as dt
import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from fetch_openalex import connect, fetch_page, upsert_work

DB_PATH = Path("erjor_citations.sqlite")
DEFAULT_MAILTO = "freddy.frost@lhch.nhs.uk"

st.set_page_config(page_title="ERJOR Citation Trends", layout="wide")
st.title("ERJ Open Research citation trends")
st.caption("Free prototype using OpenAlex citation counts and local daily snapshots.")


def snapshot_exists_for_today(db_path: Path) -> bool:
    if not db_path.exists():
        return False
    try:
        con = sqlite3.connect(db_path)
        today = dt.date.today().isoformat()
        row = con.execute(
            "SELECT COUNT(*) FROM citation_snapshots WHERE snapshot_date = ?", (today,)
        ).fetchone()
        con.close()
        return bool(row and row[0] > 0)
    except sqlite3.Error:
        return False


def fetch_latest_data(db_path: Path, mailto: str = DEFAULT_MAILTO) -> int:
    """Fetch today's ERJOR snapshot from OpenAlex into SQLite."""
    con = connect(str(db_path))
    cursor = "*"
    total = 0
    snapshot_date = dt.date.today().isoformat()

    progress = st.progress(0, text="Fetching ERJOR works from OpenAlex...")
    while True:
        data = fetch_page(cursor, mailto)
        results = data.get("results", [])
        if not results:
            break
        with con:
            for work in results:
                upsert_work(con, work, snapshot_date)
                total += 1
        progress.progress(min(95, total % 200), text=f"Fetched {total:,} works...")
        next_cursor = data.get("meta", {}).get("next_cursor")
        if not next_cursor or next_cursor == cursor:
            break
        cursor = next_cursor
    con.close()
    progress.progress(100, text=f"Fetched {total:,} ERJOR works.")
    return total


@st.cache_data(ttl=300)
def load_data(db_path: str):
    if not Path(db_path).exists():
        return pd.DataFrame(), pd.DataFrame()
    con = sqlite3.connect(db_path)
    try:
        works = pd.read_sql_query("SELECT * FROM works", con)
        snaps = pd.read_sql_query(
            """
            SELECT s.snapshot_date, s.openalex_id, s.cited_by_count,
                   w.title, w.doi, w.publication_date, w.publication_year,
                   w.authors, w.institutions, w.landing_page_url
            FROM citation_snapshots s
            JOIN works w USING(openalex_id)
            """,
            con,
        )
    except Exception:
        works, snaps = pd.DataFrame(), pd.DataFrame()
    finally:
        con.close()
    if not snaps.empty:
        snaps["snapshot_date"] = pd.to_datetime(snaps["snapshot_date"])
        snaps["publication_date"] = pd.to_datetime(snaps["publication_date"], errors="coerce")
    return works, snaps


with st.sidebar:
    st.header("Data refresh")
    mailto = st.text_input("OpenAlex mailto", value=DEFAULT_MAILTO)
    auto_refresh = st.checkbox("Auto-fetch today's data", value=True)
    manual_refresh = st.button("Fetch latest data now")

if manual_refresh or (auto_refresh and not snapshot_exists_for_today(DB_PATH)):
    try:
        fetched = fetch_latest_data(DB_PATH, mailto=mailto.strip() or DEFAULT_MAILTO)
        st.success(f"Fetched {fetched:,} ERJOR works from OpenAlex.")
        load_data.clear()
    except Exception as exc:
        st.error(f"Could not fetch OpenAlex data: {exc}")

works, snaps = load_data(str(DB_PATH))

if snaps.empty:
    st.warning("No citation data is available yet. Use 'Fetch latest data now' in the sidebar.")
    st.stop()

latest_date = snaps["snapshot_date"].max()
latest = snaps[snaps["snapshot_date"] == latest_date].copy()

pivot = snaps.pivot_table(index="openalex_id", columns="snapshot_date", values="cited_by_count", aggfunc="max")
all_dates = sorted(snaps["snapshot_date"].unique())


def delta_since(days: int) -> pd.Series:
    target = latest_date - pd.Timedelta(days=days)
    prior_dates = [d for d in all_dates if d <= target]
    if not prior_dates:
        return pd.Series(0, index=pivot.index)
    prior = max(prior_dates)
    return (pivot[latest_date] - pivot[prior]).fillna(0).astype(int)


latest = latest.set_index("openalex_id")
latest["gain_7d"] = delta_since(7)
latest["gain_30d"] = delta_since(30)
latest["gain_90d"] = delta_since(90)
latest = latest.reset_index()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Articles tracked", f"{latest['openalex_id'].nunique():,}")
col2.metric("Total citations", f"{latest['cited_by_count'].sum():,}")
col3.metric("Citations gained, 30d", f"{int(latest['gain_30d'].sum()):,}")
col4.metric("Latest snapshot", latest_date.date().isoformat())

st.divider()

total_by_day = snaps.groupby("snapshot_date", as_index=False)["cited_by_count"].sum()
total_by_day["new_citations"] = total_by_day["cited_by_count"].diff().fillna(0)

st.subheader("Total citations over time")
st.plotly_chart(px.line(total_by_day, x="snapshot_date", y="cited_by_count", markers=True), use_container_width=True)

st.subheader("New citations by snapshot")
st.plotly_chart(px.bar(total_by_day, x="snapshot_date", y="new_citations"), use_container_width=True)

st.subheader("Fastest-rising papers")
window = st.radio("Momentum window", ["7d", "30d", "90d"], horizontal=True, index=1)
metric_col = {"7d": "gain_7d", "30d": "gain_30d", "90d": "gain_90d"}[window]
top = latest.sort_values(metric_col, ascending=False).head(20)
st.dataframe(
    top[["title", "publication_date", "cited_by_count", metric_col, "doi", "landing_page_url"]],
    use_container_width=True,
    hide_index=True,
)

st.subheader("Citation age curve")
age_df = latest.dropna(subset=["publication_date"]).copy()
age_df["months_since_publication"] = ((latest_date - age_df["publication_date"]).dt.days / 30.44).round(1)
age_df = age_df[age_df["months_since_publication"] >= 0]
if not age_df.empty:
    st.plotly_chart(
        px.scatter(
            age_df,
            x="months_since_publication",
            y="cited_by_count",
            hover_name="title",
            trendline="ols",
        ),
        use_container_width=True,
    )

st.subheader("Publication-year cohorts")
cohorts = latest.groupby("publication_year", as_index=False).agg(
    papers=("openalex_id", "nunique"),
    citations=("cited_by_count", "sum"),
    gain_30d=("gain_30d", "sum"),
)
cohorts["citations_per_paper"] = (cohorts["citations"] / cohorts["papers"]).round(1)
st.dataframe(cohorts.sort_values("publication_year", ascending=False), use_container_width=True, hide_index=True)

st.subheader("Search articles")
q = st.text_input("Filter by title, DOI, author, or institution")
filtered = latest.copy()
if q:
    q_lower = q.lower()
    mask = (
        filtered["title"].fillna("").str.lower().str.contains(q_lower)
        | filtered["doi"].fillna("").str.lower().str.contains(q_lower)
        | filtered["authors"].fillna("").str.lower().str.contains(q_lower)
        | filtered["institutions"].fillna("").str.lower().str.contains(q_lower)
    )
    filtered = filtered[mask]
st.dataframe(
    filtered.sort_values("cited_by_count", ascending=False)[["title", "publication_date", "cited_by_count", "gain_30d", "authors", "doi"]],
    use_container_width=True,
    hide_index=True,
)
