from __future__ import annotations

import datetime as dt
import json
import re
import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from fetch_openalex import DEFAULT_MAX_AGE_MONTHS, DEFAULT_MIN_AGE_MONTHS, connect, fetch_window, publication_window

DB_PATH = Path("erjor_citations.sqlite")
DEFAULT_MAILTO = "freddy.frost@lhch.nhs.uk"

st.set_page_config(page_title="ERJOR Editorial Intelligence", layout="wide")
st.title("ERJ Open Research Editorial Intelligence Dashboard")
st.caption("Free prototype using OpenAlex. Citation counts may differ from Google Scholar; first-12-month citations are estimated from OpenAlex annual citation buckets.")

DISEASE_THEME_RULES = {
    "Bronchiectasis": ["bronchiectasis", "ntm", "nontuberculous mycobacter"],
    "COPD": ["copd", "chronic obstructive", "emphysema"],
    "Asthma": ["asthma", "eosinophil", "airway hyperresponsiveness"],
    "ILD": ["interstitial lung", "ild", "pulmonary fibrosis", "sarcoidosis", "hypersensitivity pneumonitis"],
    "Pulmonary vascular disease": ["pulmonary hypertension", "pulmonary vascular", "embolism"],
    "Respiratory infection": ["infection", "pneumonia", "tuberculosis", "covid", "influenza", "virus", "bacterial"],
    "Lung cancer": ["lung cancer", "thoracic oncology", "mesothelioma", "tumour", "tumor", "neoplasm"],
    "Sleep medicine": ["sleep", "obstructive sleep apnoea", "obstructive sleep apnea", "osa"],
    "Pulmonary rehabilitation": ["pulmonary rehabilitation", "exercise", "physical activity", "rehabilitation"],
    "Critical care": ["critical care", "intensive care", "icu", "ards", "ventilation", "mechanical ventilation"],
    "Respiratory physiology": ["physiology", "lung function", "spirometry", "gas exchange", "ventilatory"],
    "Imaging": ["imaging", "ct", "computed tomography", "radiology", "ultrasound", "mri"],
    "Digital health": ["digital", "telemedicine", "remote monitoring", "wearable", "app", "machine learning", "artificial intelligence", " ai "],
    "Airway disease": ["airway", "small airways", "airflow", "obstructive airway"],
    "Environmental/occupational": ["environment", "occupational", "pollution", "air quality", "exposure", "smoking", "vaping"],
    "Rare lung disease": ["rare", "alpha-1", "lymphangioleiomyomatosis", "lam", "cystic fibrosis"],
}

METHOD_THEME_RULES = {
    "Clinical research": ["cohort", "patient", "clinical", "mortality", "prognosis", "trial", "registry", "observational", "case-control"],
    "Basic science": ["mouse", "mice", "cell", "in vitro", "molecular", "pathway", "animal model", "mechanism"],
    "Translational research": ["biomarker", "translational", "phenotype", "endotype", "omics", "genomic", "proteomic"],
    "Epidemiology": ["epidemiology", "prevalence", "incidence", "population", "burden"],
    "Health services research": ["health service", "quality of care", "implementation", "pathway", "service", "access"],
    "Clinical trials": ["randomised", "randomized", "trial", "placebo", "phase 2", "phase ii", "phase 3", "phase iii"],
    "Systematic review/meta-analysis": ["systematic review", "meta-analysis", "meta analysis"],
    "Artificial intelligence": ["artificial intelligence", "machine learning", "deep learning", "algorithm", " ai "],
    "Implementation science": ["implementation", "adoption", "feasibility", "barrier", "facilitator"],
}


def json_text(value: str | None) -> str:
    if not value:
        return ""
    try:
        parsed = json.loads(value)
    except Exception:
        return str(value)
    chunks: list[str] = []
    def walk(x):
        if isinstance(x, dict):
            for key in ("display_name", "name", "description"):
                if x.get(key):
                    chunks.append(str(x[key]))
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for item in x:
                walk(item)
    walk(parsed)
    return " ".join(chunks)


def tag_themes(row: pd.Series) -> list[str]:
    text = " ".join(str(row.get(c) or "") for c in ["title", "work_type", "article_type"])
    text += " " + json_text(row.get("concepts_json")) + " " + json_text(row.get("topics_json")) + " " + json_text(row.get("keywords_json"))
    haystack = f" {text.lower()} "
    themes = []
    for theme, terms in {**DISEASE_THEME_RULES, **METHOD_THEME_RULES}.items():
        for term in terms:
            if term.strip() in haystack:
                themes.append(theme)
                break
    if not themes:
        themes.append("Other/uncategorised")
    return themes


def estimate_first_12m_citations(row: pd.Series) -> int:
    """Approximate citations accrued in first 365 days using counts_by_year.

    OpenAlex counts_by_year has annual citation buckets. We prorate a citation
    year by how much of that calendar year overlaps the first 365 days after
    publication. This is an estimate, not an exact first-year citation count.
    """
    pub = pd.to_datetime(row.get("publication_date"), errors="coerce")
    if pd.isna(pub):
        return 0
    try:
        counts = json.loads(row.get("counts_by_year_json") or "[]")
    except Exception:
        counts = []
    start = pub.date()
    end = start + dt.timedelta(days=365)
    total = 0.0
    for item in counts:
        year = int(item.get("year", 0) or 0)
        count = int(item.get("cited_by_count", 0) or 0)
        if not year or not count:
            continue
        y0, y1 = dt.date(year, 1, 1), dt.date(year + 1, 1, 1)
        overlap = max(0, (min(end, y1) - max(start, y0)).days)
        if overlap:
            total += count * (overlap / (y1 - y0).days)
    # For very recent papers, current count is a better lower-bound than empty annual buckets.
    age_days = (dt.date.today() - start).days
    if 0 <= age_days <= 365 and total == 0:
        return int(row.get("cited_by_count") or 0)
    return int(round(total))


def snapshot_exists_for_today(db_path: Path) -> bool:
    if not db_path.exists():
        return False
    try:
        con = sqlite3.connect(db_path)
        today = dt.date.today().isoformat()
        row = con.execute("SELECT COUNT(*) FROM citation_snapshots WHERE snapshot_date = ?", (today,)).fetchone()
        con.close()
        return bool(row and row[0] > 0)
    except sqlite3.Error:
        return False


def fetch_latest_data(db_path: Path, mailto: str, min_age_months: int, max_age_months: int) -> int:
    connect(str(db_path)).close()
    today = dt.date.today()
    start_date, end_date = publication_window(today, min_age_months, max_age_months)
    progress = st.progress(0, text=f"Fetching ERJOR works published {start_date} to {end_date} from OpenAlex...")
    total = fetch_window(str(db_path), mailto, start_date, end_date, today.isoformat())
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
                   w.work_type, w.article_type, w.authors, w.first_author,
                   w.institutions, w.landing_page_url, w.concepts_json,
                   w.topics_json, w.keywords_json, w.counts_by_year_json
            FROM citation_snapshots s
            JOIN works w USING(openalex_id)
            """,
            con,
        )
    except Exception:
        works, snaps = pd.DataFrame(), pd.DataFrame()
    finally:
        con.close()
    for df in (works, snaps):
        if not df.empty and "publication_date" in df:
            df["publication_date"] = pd.to_datetime(df["publication_date"], errors="coerce")
    if not snaps.empty:
        snaps["snapshot_date"] = pd.to_datetime(snaps["snapshot_date"])
    return works, snaps


def enrich_latest(snaps: pd.DataFrame, min_age: int, max_age: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.Timestamp]:
    latest_date = snaps["snapshot_date"].max()
    latest = snaps[snaps["snapshot_date"] == latest_date].copy()
    start, end = publication_window(dt.date.today(), min_age, max_age)
    latest = latest[(latest["publication_date"] >= pd.to_datetime(start)) & (latest["publication_date"] <= pd.to_datetime(end))].copy()
    snaps2 = snaps[snaps["openalex_id"].isin(latest["openalex_id"])]
    if latest.empty:
        return latest, snaps2, latest_date
    pivot = snaps2.pivot_table(index="openalex_id", columns="snapshot_date", values="cited_by_count", aggfunc="max")
    all_dates = sorted(snaps2["snapshot_date"].unique())
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
    latest["months_since_publication"] = ((latest_date - latest["publication_date"]).dt.days / 30.44).round(1)
    latest["citations_per_month"] = (latest["cited_by_count"] / latest["months_since_publication"].clip(lower=0.25)).round(2)
    latest["themes"] = latest.apply(tag_themes, axis=1)
    latest["theme"] = latest["themes"].apply(lambda x: "; ".join(x))
    latest["estimated_first_12m_citations"] = latest.apply(estimate_first_12m_citations, axis=1)
    return latest, snaps2, latest_date


def explode_themes(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.explode("themes").rename(columns={"themes": "theme_tag"})
    return out


with st.sidebar:
    st.header("Data refresh")
    mailto = st.text_input("OpenAlex mailto", value=DEFAULT_MAILTO)
    auto_refresh = st.checkbox("Auto-fetch today's data", value=True)
    manual_refresh = st.button("Fetch latest data now")
    st.caption("The app fetches 0-36 months of papers so both recent and 12-36m pages work.")

if manual_refresh or (auto_refresh and not snapshot_exists_for_today(DB_PATH)):
    try:
        fetched = fetch_latest_data(DB_PATH, mailto.strip() or DEFAULT_MAILTO, min_age_months=0, max_age_months=36)
        st.success(f"Fetched {fetched:,} ERJOR works from OpenAlex.")
        load_data.clear()
    except Exception as exc:
        st.error(f"Could not fetch OpenAlex data: {exc}")

works, snaps = load_data(str(DB_PATH))
if snaps.empty:
    st.warning("No citation data is available yet. Use 'Fetch latest data now' in the sidebar.")
    st.stop()

page = st.sidebar.radio("Pages", ["Citation performance: 12-36m", "New papers: 0-12m", "Top 25 papers", "Topic momentum"])

if page == "Citation performance: 12-36m":
    latest, snaps2, latest_date = enrich_latest(snaps, 12, 36)
    st.header("Citation performance: papers published 12-36 months ago")
    if latest.empty:
        st.warning("No papers found in the 12-36 month window. Fetch latest data and try again.")
        st.stop()
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Papers", f"{latest['openalex_id'].nunique():,}")
    c2.metric("Est. first-12m citations", f"{int(latest['estimated_first_12m_citations'].sum()):,}")
    c3.metric("Current citations", f"{int(latest['cited_by_count'].sum()):,}")
    c4.metric("Median first-12m cites", f"{latest['estimated_first_12m_citations'].median():.0f}")
    c5.metric("% with >=10 first-12m cites", f"{(latest['estimated_first_12m_citations'].ge(10).mean()*100):.0f}%")
    st.info("First-12-month citations are estimated from OpenAlex annual citation buckets; exact month-level citing dates are not available in the free OpenAlex works endpoint.")
    total_by_day = snaps2.groupby("snapshot_date", as_index=False)["cited_by_count"].sum()
    total_by_day["new_citations"] = total_by_day["cited_by_count"].diff().fillna(0)
    st.subheader("Citation trend for the 12-36m cohort")
    st.plotly_chart(px.line(total_by_day, x="snapshot_date", y="cited_by_count", markers=True), use_container_width=True)
    st.subheader("First-12-month citation distribution")
    st.plotly_chart(px.histogram(latest, x="estimated_first_12m_citations", nbins=30), use_container_width=True)

elif page == "New papers: 0-12m":
    latest, snaps2, latest_date = enrich_latest(snaps, 0, 12)
    st.header("New papers: published in the last 12 months")
    if latest.empty:
        st.warning("No papers found in the 0-12 month window. Fetch latest data and try again.")
        st.stop()
    regularly = latest[(latest["cited_by_count"] >= 3) | (latest["citations_per_month"] >= 0.5)].copy()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("New papers", f"{latest['openalex_id'].nunique():,}")
    c2.metric("Current citations", f"{int(latest['cited_by_count'].sum()):,}")
    c3.metric("Cited regularly", f"{regularly['openalex_id'].nunique():,}")
    c4.metric("Median citations/month", f"{latest['citations_per_month'].median():.2f}")
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Article type breakdown")
        type_df = latest.groupby("article_type", as_index=False).agg(papers=("openalex_id", "nunique"), citations=("cited_by_count", "sum"))
        st.plotly_chart(px.bar(type_df.sort_values("papers", ascending=False), x="article_type", y="papers", hover_data=["citations"]), use_container_width=True)
        st.dataframe(type_df.sort_values("papers", ascending=False), use_container_width=True, hide_index=True)
    with col_b:
        st.subheader("Theme breakdown")
        th = explode_themes(latest).groupby("theme_tag", as_index=False).agg(papers=("openalex_id", "nunique"), citations=("cited_by_count", "sum"))
        st.plotly_chart(px.bar(th.sort_values("papers", ascending=False).head(20), x="theme_tag", y="papers", hover_data=["citations"]), use_container_width=True)
        st.dataframe(th.sort_values(["papers", "citations"], ascending=False), use_container_width=True, hide_index=True)
    st.subheader("Recent papers already being cited regularly")
    st.caption("Flagged if citations >=3 or citations/month >=0.5. These thresholds can be changed later.")
    st.dataframe(
        latest.sort_values(["citations_per_month", "cited_by_count"], ascending=False)[["title", "first_author", "article_type", "theme", "publication_date", "months_since_publication", "cited_by_count", "citations_per_month", "doi", "landing_page_url"]],
        use_container_width=True,
        hide_index=True,
    )

elif page == "Top 25 papers":
    st.header("Top 25 cited papers")
    min_age, max_age = st.slider("Publication age window, months", 0, 36, (12, 36))
    latest, _, _ = enrich_latest(snaps, min_age, max_age)
    if latest.empty:
        st.warning("No papers found in this window.")
        st.stop()
    top25 = latest.sort_values("cited_by_count", ascending=False).head(25)
    st.dataframe(
        top25[["title", "first_author", "theme", "cited_by_count", "estimated_first_12m_citations", "publication_date", "publication_year", "article_type", "doi", "landing_page_url"]],
        use_container_width=True,
        hide_index=True,
    )

elif page == "Topic momentum":
    st.header("Topics generating citation momentum")
    min_age, max_age = st.slider("Publication age window, months", 0, 36, (0, 36))
    latest, _, _ = enrich_latest(snaps, min_age, max_age)
    if latest.empty:
        st.warning("No papers found in this window.")
        st.stop()
    th = explode_themes(latest)
    theme_stats = th.groupby("theme_tag", as_index=False).agg(
        papers=("openalex_id", "nunique"),
        citations=("cited_by_count", "sum"),
        gain_30d=("gain_30d", "sum"),
        gain_90d=("gain_90d", "sum"),
        mean_citations=("cited_by_count", "mean"),
        median_citations=("cited_by_count", "median"),
        mean_citations_per_month=("citations_per_month", "mean"),
    )
    theme_stats["citations_per_paper"] = (theme_stats["citations"] / theme_stats["papers"]).round(2)
    theme_stats["momentum_score"] = (theme_stats["gain_30d"] + theme_stats["mean_citations_per_month"]).round(2)
    theme_stats = theme_stats.sort_values(["momentum_score", "citations_per_paper"], ascending=False)
    st.subheader("Theme momentum table")
    st.dataframe(theme_stats, use_container_width=True, hide_index=True)
    st.subheader("Citation momentum by theme")
    st.plotly_chart(px.bar(theme_stats.head(20), x="theme_tag", y="momentum_score", hover_data=["papers", "citations", "gain_30d", "citations_per_paper"]), use_container_width=True)
    st.subheader("Top paper within each theme")
    top_by_theme = th.sort_values("cited_by_count", ascending=False).groupby("theme_tag", as_index=False).head(1)
    st.dataframe(top_by_theme[["theme_tag", "title", "first_author", "publication_date", "cited_by_count", "gain_30d", "citations_per_month", "doi"]], use_container_width=True, hide_index=True)
