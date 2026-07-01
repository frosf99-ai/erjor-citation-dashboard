from __future__ import annotations

import datetime as dt
import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Iterable

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from fetch_openalex import connect, fetch_window, publication_window

DB_PATH = Path("erjor_citations.sqlite")
DEFAULT_MAILTO = os.environ.get("OPENALEX_MAILTO", "freddy.frost@lhch.nhs.uk")
TODAY = dt.date.today()

ERJ_BLUE = "#004B93"
ERJ_DARK_BLUE = "#003366"
ERJ_RED = "#E30613"
ERJ_TEAL = "#008C95"
ERJ_PURPLE = "#5B4BB2"
ERJ_GREY = "#667085"
ERJ_LIGHT = "#F6F8FB"
PLOTLY_COLORS = [ERJ_BLUE, ERJ_RED, ERJ_TEAL, ERJ_PURPLE, "#7A869A", "#00A3E0", "#E87722"]

st.set_page_config(
    page_title="ERJOR Editorial Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

DISEASE_THEME_RULES = {
    "Bronchiectasis": ["bronchiectasis", "ntm", "nontuberculous mycobacter"],
    "COPD": ["copd", "chronic obstructive", "emphysema"],
    "Asthma": ["asthma", "eosinophil", "airway hyperresponsiveness"],
    "ILD": ["interstitial lung", "ild", "pulmonary fibrosis", "sarcoidosis", "hypersensitivity pneumonitis"],
    "Pulmonary vascular disease": ["pulmonary hypertension", "pulmonary vascular", "embolism"],
    "Respiratory infection": ["infection", "pneumonia", "tuberculosis", "covid", "influenza", "virus", "bacterial", "mycobacter"],
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
    "Clinical research": ["cohort", "patient", "clinical", "mortality", "prognosis", "registry", "observational", "case-control", "case control", "outcome"],
    "Basic science": ["mouse", "mice", "cell", "in vitro", "molecular", "pathway", "animal model", "mechanism", "gene", "protein"],
    "Translational research": ["biomarker", "translational", "phenotype", "endotype", "omics", "genomic", "proteomic", "precision medicine"],
    "Epidemiology": ["epidemiology", "prevalence", "incidence", "population", "burden", "risk factor"],
    "Health services research": ["health service", "quality of care", "implementation", "pathway", "service", "access", "delivery"],
    "Clinical trials": ["randomised", "randomized", "trial", "placebo", "phase 2", "phase ii", "phase 3", "phase iii"],
    "Systematic review/meta-analysis": ["systematic review", "meta-analysis", "meta analysis"],
    "Artificial intelligence": ["artificial intelligence", "machine learning", "deep learning", "algorithm", " ai "],
    "Implementation science": ["implementation", "adoption", "feasibility", "barrier", "facilitator"],
}


def inject_css() -> None:
    st.markdown(
        f"""
        <style>
        :root {{
            --erj-blue: {ERJ_BLUE};
            --erj-dark-blue: {ERJ_DARK_BLUE};
            --erj-red: {ERJ_RED};
            --erj-light: {ERJ_LIGHT};
        }}
        .stApp {{ background: #ffffff; }}
        section[data-testid="stSidebar"] {{
            background: linear-gradient(180deg, #003B71 0%, #004B93 48%, #002B52 100%);
        }}
        section[data-testid="stSidebar"] * {{ color: white !important; }}
        section[data-testid="stSidebar"] .stRadio label {{
            padding: 0.35rem 0.2rem;
            border-radius: 12px;
        }}
        div[data-testid="stMetric"] {{
            background: #fff;
            border: 1px solid #D8DEE9;
            border-radius: 14px;
            padding: 18px 18px 14px 18px;
            box-shadow: 0 2px 10px rgba(16, 24, 40, 0.04);
            min-height: 132px;
        }}
        div[data-testid="stMetricLabel"] p {{
            color: {ERJ_BLUE} !important;
            font-weight: 800 !important;
            text-transform: uppercase;
            font-size: 0.78rem !important;
            letter-spacing: .02em;
        }}
        div[data-testid="stMetricValue"] {{
            color: #101828;
            font-weight: 900;
        }}
        .block-container {{ padding-top: 1.4rem; padding-bottom: 2rem; }}
        .erj-header {{
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 24px;
            margin-bottom: 1.0rem;
        }}
        .erj-title h1 {{
            color: #101828;
            font-size: 2.25rem;
            font-weight: 900;
            margin: 0;
            line-height: 1.1;
        }}
        .erj-title p {{
            color: #53637A;
            font-size: 1.15rem;
            margin: 0.45rem 0 0 0;
        }}
        .erj-brand {{
            min-width: 280px;
            text-align: left;
            border-left: 1px solid #D8DEE9;
            padding-left: 24px;
            color: {ERJ_BLUE};
            font-weight: 800;
            letter-spacing: .02em;
            line-height: 1.15;
        }}
        .erj-brand .open {{ color: {ERJ_RED}; margin-top: 6px; }}
        .erj-subnote {{
            color: #53637A;
            font-size: 0.9rem;
            margin: .4rem 0 1.2rem 0;
        }}
        .section-card {{
            background: #fff;
            border: 1px solid #D8DEE9;
            border-radius: 14px;
            padding: 16px 18px;
            box-shadow: 0 2px 10px rgba(16, 24, 40, 0.04);
            margin-bottom: 14px;
        }}
        .section-card h3 {{
            color: {ERJ_BLUE};
            text-transform: uppercase;
            font-size: 0.9rem;
            letter-spacing: .02em;
            margin-top: 0;
        }}
        .sidebar-logo {{
            display: flex;
            align-items: center;
            gap: 12px;
            margin: 0 0 24px 0;
            padding: 16px 8px 12px 4px;
        }}
        .logo-dot {{
            width: 54px;
            height: 54px;
            border-radius: 50%;
            background: {ERJ_RED};
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: 900;
            font-size: 1.15rem;
            box-shadow: 0 5px 18px rgba(0,0,0,.18);
        }}
        .logo-text {{ line-height: 1.05; }}
        .logo-text .erj {{ font-size: 2.2rem; font-weight: 900; letter-spacing: .02em; }}
        .logo-text .or {{ font-size: .95rem; font-weight: 800; }}
        .sidebar-footer {{
            margin-top: 36px;
            padding-top: 20px;
            border-top: 1px solid rgba(255,255,255,.35);
            font-size: 0.85rem;
            line-height: 1.45;
            opacity: .95;
        }}
        .pill {{
            display: inline-block;
            background: #EEF4FF;
            color: {ERJ_BLUE};
            border: 1px solid #C7D7FE;
            border-radius: 999px;
            padding: 3px 10px;
            margin: 2px 4px 2px 0;
            font-size: 0.78rem;
            font-weight: 700;
        }}
        div[data-testid="stDataFrame"] {{ border: 1px solid #D8DEE9; border-radius: 12px; }}
        button[kind="primary"] {{ background: {ERJ_BLUE} !important; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def sidebar_logo() -> None:
    st.sidebar.markdown(
        """
        <div class="sidebar-logo">
          <div class="logo-dot">ERJ</div>
          <div class="logo-text"><div class="erj">ERJ</div><div class="or">OPEN RESEARCH</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def page_header(title: str, subtitle: str, cohort: str | None = None, updated: str | None = None) -> None:
    details = []
    if cohort:
        details.append(f"Analysis period: {cohort}")
    if updated:
        details.append(f"Updated: {updated}")
    details_text = " &nbsp; | &nbsp; ".join(details)
    st.markdown(
        f"""
        <div class="erj-header">
          <div class="erj-title">
            <h1>{title}</h1>
            <p>{subtitle}</p>
            <div class="erj-subnote">ⓘ {details_text}</div>
          </div>
          <div class="erj-brand">
            EUROPEAN RESPIRATORY<br/>JOURNAL
            <div class="open">OPEN RESEARCH</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_title(title: str, caption: str | None = None) -> None:
    cap = f"<div style='color:{ERJ_GREY}; font-size:.9rem; margin-top:-.35rem'>{caption}</div>" if caption else ""
    st.markdown(f"<h3 style='color:{ERJ_BLUE}; text-transform:uppercase; font-size:.95rem; letter-spacing:.02em'>{title}</h3>{cap}", unsafe_allow_html=True)


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
            for key in ("display_name", "name", "description", "keyword"):
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
        if any(term.strip() in haystack for term in terms):
            themes.append(theme)
    return themes or ["Other/uncategorised"]


def citation_count_between(row: pd.Series, start: dt.date, end: dt.date) -> int:
    """Estimate citations from citing works published within date window.

    OpenAlex gives counts_by_year rather than exact citing dates in the basic work
    record. We prorate each calendar-year citation bucket by the overlap with the
    requested window. This is a good dashboard estimate; exact values require
    fetching every citing work and checking its publication date.
    """
    try:
        counts = json.loads(row.get("counts_by_year_json") or "[]")
    except Exception:
        counts = []
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
    return int(round(total))


def last_365_citations(row: pd.Series, as_of: dt.date) -> int:
    return citation_count_between(row, as_of - dt.timedelta(days=365), as_of)


def first_12m_citations(row: pd.Series) -> int:
    pub = pd.to_datetime(row.get("publication_date"), errors="coerce")
    if pd.isna(pub):
        return 0
    start = pub.date()
    return citation_count_between(row, start, start + dt.timedelta(days=365))


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


def fetch_latest_data(db_path: Path, mailto: str, min_age_months: int = 0, max_age_months: int = 36) -> int:
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


def enrich_latest(snaps: pd.DataFrame, min_age: int, max_age: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.Timestamp, str]:
    latest_date = snaps["snapshot_date"].max()
    latest = snaps[snaps["snapshot_date"] == latest_date].copy()
    start, end = publication_window(dt.date.today(), min_age, max_age)
    latest = latest[(latest["publication_date"] >= pd.to_datetime(start)) & (latest["publication_date"] <= pd.to_datetime(end))].copy()
    snaps2 = snaps[snaps["openalex_id"].isin(latest["openalex_id"])]
    if latest.empty:
        return latest, snaps2, latest_date, f"{start} to {end}"

    pivot = snaps2.pivot_table(index="openalex_id", columns="snapshot_date", values="cited_by_count", aggfunc="max")
    all_dates = sorted(snaps2["snapshot_date"].unique())

    def delta_since(days: int) -> pd.Series:
        target = latest_date - pd.Timedelta(days=days)
        prior_dates = [d for d in all_dates if d <= target]
        if not prior_dates or latest_date not in pivot.columns:
            return pd.Series(0, index=pivot.index)
        prior = max(prior_dates)
        return (pivot[latest_date] - pivot[prior]).fillna(0).astype(int)

    latest = latest.set_index("openalex_id")
    latest["gain_7d"] = delta_since(7)
    latest["gain_30d"] = delta_since(30)
    latest["gain_90d"] = delta_since(90)
    latest = latest.reset_index()
    latest["months_since_publication"] = ((latest_date - latest["publication_date"]).dt.days / 30.44).clip(lower=0).round(1)
    latest["citations_per_month"] = (latest["cited_by_count"] / latest["months_since_publication"].clip(lower=0.25)).round(2)
    latest["themes"] = latest.apply(tag_themes, axis=1)
    latest["theme"] = latest["themes"].apply(lambda x: "; ".join(x))
    as_of = latest_date.date() if hasattr(latest_date, "date") else dt.date.today()
    latest["citations_365d"] = latest.apply(lambda r: last_365_citations(r, as_of), axis=1)
    latest["first_12m_citations"] = latest.apply(first_12m_citations, axis=1)
    latest["citation_momentum_index"] = (latest["citations_365d"] / latest["cited_by_count"].replace(0, pd.NA)).fillna(0).round(2)
    return latest, snaps2, latest_date, f"{start} to {end}"


def explode_themes(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    return df.explode("themes").rename(columns={"themes": "theme_tag"})


def prep_table(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "publication_date" in out:
        out["publication_date"] = pd.to_datetime(out["publication_date"]).dt.date.astype(str)
    return out


def chart_layout(fig: go.Figure) -> go.Figure:
    fig.update_layout(
        template="plotly_white",
        colorway=PLOTLY_COLORS,
        font=dict(family="Arial", color="#101828"),
        margin=dict(l=10, r=10, t=35, b=10),
        paper_bgcolor="white",
        plot_bgcolor="white",
        legend=dict(orientation="v"),
    )
    fig.update_xaxes(showgrid=True, gridcolor="#EDF1F7")
    fig.update_yaxes(showgrid=True, gridcolor="#EDF1F7")
    return fig


def metric_row_12_36(latest: pd.DataFrame) -> None:
    top = latest.sort_values("citations_365d", ascending=False).head(1)
    top_title = "—" if top.empty else re.sub(r"\s+", " ", str(top.iloc[0]["title"]))[:62]
    top_value = 0 if top.empty else int(top.iloc[0]["citations_365d"])
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Papers published (12-36 months)", f"{latest['openalex_id'].nunique():,}")
    c2.metric("Lifetime citations", f"{int(latest['cited_by_count'].sum()):,}")
    c3.metric("Citations in last 365 days", f"{int(latest['citations_365d'].sum()):,}")
    c4.metric("Mean citations in last 365 days per paper", f"{latest['citations_365d'].mean():.1f}")
    c5.metric("Most cited paper (last 365 days)", f"{top_value:,}", delta=top_title)
    c6.metric("Median citations in last 365 days", f"{latest['citations_365d'].median():.0f}")


def citation_performance(snaps: pd.DataFrame) -> None:
    latest, snaps2, latest_date, cohort = enrich_latest(snaps, 12, 36)
    page_header("Citation Performance (12–36 Month Cohort)", "Papers published between 12 and 36 months ago", cohort, latest_date.date().isoformat())
    if latest.empty:
        st.warning("No papers found in the 12–36 month window. Use the sidebar to fetch data.")
        return
    metric_row_12_36(latest)

    col1, col2, col3, col4 = st.columns([1.25, 1, 1.15, 1.15])
    with col1:
        section_title("Citations in last 365 days over time")
        monthly = snaps2.copy()
        monthly["month"] = monthly["snapshot_date"].dt.to_period("M").dt.to_timestamp()
        monthly = monthly.groupby("month", as_index=False)["cited_by_count"].sum().sort_values("month")
        monthly["monthly_gain"] = monthly["cited_by_count"].diff().fillna(0).clip(lower=0)
        fig = px.line(monthly.tail(13), x="month", y="monthly_gain", markers=True)
        fig.update_traces(line_color=ERJ_RED, marker_color=ERJ_RED)
        st.plotly_chart(chart_layout(fig), use_container_width=True)
    with col2:
        section_title("Distribution of citations (365d)")
        fig = px.histogram(latest, x="citations_365d", nbins=24)
        fig.update_traces(marker_color=ERJ_BLUE)
        st.plotly_chart(chart_layout(fig), use_container_width=True)
    with col3:
        section_title("Top themes by citations (365d)")
        th = explode_themes(latest).groupby("theme_tag", as_index=False).agg(citations_365d=("citations_365d", "sum"), papers=("openalex_id", "nunique"))
        th = th.sort_values("citations_365d", ascending=False).head(8)
        fig = px.bar(th, x="citations_365d", y="theme_tag", orientation="h", hover_data=["papers"])
        fig.update_traces(marker_color=ERJ_BLUE)
        fig.update_layout(yaxis={"categoryorder":"total ascending"})
        st.plotly_chart(chart_layout(fig), use_container_width=True)
    with col4:
        section_title("Article types by citations (365d)")
        ty = latest.groupby("article_type", as_index=False).agg(citations_365d=("citations_365d", "sum"), papers=("openalex_id", "nunique"))
        fig = px.pie(ty, values="citations_365d", names="article_type", hole=.55, color_discrete_sequence=PLOTLY_COLORS)
        st.plotly_chart(chart_layout(fig), use_container_width=True)

    left, right = st.columns([1.45, 1])
    with left:
        section_title("Top 25 papers by citations in last 365 days")
        top25 = latest.sort_values(["citations_365d", "cited_by_count"], ascending=False).head(25)
        cols = ["title", "first_author", "theme", "article_type", "publication_date", "citations_365d", "cited_by_count", "doi", "landing_page_url"]
        st.dataframe(prep_table(top25[cols]), use_container_width=True, hide_index=True)
        st.download_button("Download top 25 CSV", prep_table(top25[cols]).to_csv(index=False), "erjor_top25_citations_365d.csv", "text/csv")
    with right:
        section_title("Lifetime citations vs citations in last 365 days")
        fig = px.scatter(latest, x="cited_by_count", y="citations_365d", hover_name="title", hover_data=["first_author", "article_type"], trendline="ols")
        fig.update_traces(marker=dict(color=ERJ_BLUE, size=8, opacity=.78))
        st.plotly_chart(chart_layout(fig), use_container_width=True)

    st.caption("Citations in the last 365 days are estimated from OpenAlex counts_by_year for citing works. Lifetime citations use OpenAlex cited_by_count and may differ from Google Scholar.")


def new_papers(snaps: pd.DataFrame) -> None:
    latest, _, latest_date, cohort = enrich_latest(snaps, 0, 12)
    page_header("New Papers (0–12 Months)", "Theme, article type and early citation traction", cohort, latest_date.date().isoformat())
    if latest.empty:
        st.warning("No papers found in the last 12 months.")
        return
    regularly = latest[(latest["cited_by_count"] >= 3) | (latest["citations_per_month"] >= 0.5)].copy()
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Total papers", f"{latest['openalex_id'].nunique():,}")
    c2.metric("Original research", f"{latest['article_type'].str.contains('Original', case=False, na=False).sum():,}")
    c3.metric("Reviews", f"{latest['article_type'].str.contains('Review', case=False, na=False).sum():,}")
    c4.metric("Clinical research", f"{explode_themes(latest).query('theme_tag == " + '"Clinical research"' + "')['openalex_id'].nunique():,}")
    c5.metric("Basic science", f"{explode_themes(latest).query('theme_tag == " + '"Basic science"' + "')['openalex_id'].nunique():,}")
    c6.metric("Cited regularly", f"{regularly['openalex_id'].nunique():,}")

    col1, col2 = st.columns(2)
    with col1:
        section_title("Article type breakdown")
        type_df = latest.groupby("article_type", as_index=False).agg(papers=("openalex_id", "nunique"), citations=("cited_by_count", "sum"))
        fig = px.bar(type_df.sort_values("papers", ascending=False), x="article_type", y="papers", hover_data=["citations"])
        fig.update_traces(marker_color=ERJ_BLUE)
        st.plotly_chart(chart_layout(fig), use_container_width=True)
        st.dataframe(type_df.sort_values("papers", ascending=False), use_container_width=True, hide_index=True)
    with col2:
        section_title("Theme breakdown", "Papers can have more than one theme")
        th = explode_themes(latest).groupby("theme_tag", as_index=False).agg(papers=("openalex_id", "nunique"), citations=("cited_by_count", "sum"))
        th = th.sort_values(["papers", "citations"], ascending=False)
        fig = px.bar(th.head(18), x="papers", y="theme_tag", orientation="h", hover_data=["citations"])
        fig.update_traces(marker_color=ERJ_RED)
        fig.update_layout(yaxis={"categoryorder":"total ascending"})
        st.plotly_chart(chart_layout(fig), use_container_width=True)
        st.dataframe(th, use_container_width=True, hide_index=True)

    section_title("Recent papers already gaining citation traction")
    cols = ["title", "first_author", "article_type", "theme", "publication_date", "months_since_publication", "cited_by_count", "citations_per_month", "doi", "landing_page_url"]
    st.dataframe(prep_table(latest.sort_values(["citations_per_month", "cited_by_count"], ascending=False)[cols]), use_container_width=True, hide_index=True)


def topic_momentum(snaps: pd.DataFrame) -> None:
    latest, _, latest_date, cohort = enrich_latest(snaps, 12, 36)
    page_header("Topic Momentum", "Which topics are generating current citation impact?", cohort, latest_date.date().isoformat())
    if latest.empty:
        st.warning("No papers found.")
        return
    th = explode_themes(latest)
    stats = th.groupby("theme_tag", as_index=False).agg(
        papers=("openalex_id", "nunique"),
        citations_365d=("citations_365d", "sum"),
        lifetime_citations=("cited_by_count", "sum"),
        mean_365d=("citations_365d", "mean"),
        median_365d=("citations_365d", "median"),
        gain_30d=("gain_30d", "sum"),
        gain_90d=("gain_90d", "sum"),
    )
    stats["citations_365d_per_paper"] = (stats["citations_365d"] / stats["papers"]).round(2)
    stats["momentum"] = (stats["citations_365d_per_paper"] + stats["gain_90d"] / stats["papers"].clip(lower=1)).round(2)
    stats = stats.sort_values(["momentum", "citations_365d"], ascending=False)

    col1, col2 = st.columns([1.2, 1])
    with col1:
        section_title("Theme momentum table")
        st.dataframe(stats, use_container_width=True, hide_index=True)
    with col2:
        section_title("Momentum bubble chart")
        fig = px.scatter(stats, x="papers", y="citations_365d_per_paper", size="citations_365d", color="theme_tag", hover_name="theme_tag", color_discrete_sequence=PLOTLY_COLORS)
        st.plotly_chart(chart_layout(fig), use_container_width=True)

    section_title("Top paper within each theme")
    top_by_theme = th.sort_values(["citations_365d", "cited_by_count"], ascending=False).groupby("theme_tag", as_index=False).head(1)
    cols = ["theme_tag", "title", "first_author", "publication_date", "citations_365d", "cited_by_count", "article_type", "doi"]
    st.dataframe(prep_table(top_by_theme[cols]), use_container_width=True, hide_index=True)


def editorial_intelligence(snaps: pd.DataFrame) -> None:
    cohort, _, latest_date, cohort_text = enrich_latest(snaps, 12, 36)
    recent, _, _, recent_text = enrich_latest(snaps, 0, 12)
    page_header("Editorial Intelligence", "Editor's Radar: papers and topics to act on", cohort_text, latest_date.date().isoformat())
    if cohort.empty and recent.empty:
        st.warning("No papers available.")
        return
    col1, col2 = st.columns(2)
    with col1:
        section_title("Rising stars", "12–36m papers with highest citations in the last 365 days")
        cols = ["title", "first_author", "theme", "publication_date", "citations_365d", "cited_by_count", "citation_momentum_index"]
        st.dataframe(prep_table(cohort.sort_values(["citations_365d", "citation_momentum_index"], ascending=False).head(12)[cols]), use_container_width=True, hide_index=True)
    with col2:
        section_title("High-potential new papers", "0–12m papers already cited or cited per month")
        cols = ["title", "first_author", "theme", "publication_date", "cited_by_count", "citations_per_month"]
        st.dataframe(prep_table(recent.sort_values(["citations_per_month", "cited_by_count"], ascending=False).head(12)[cols]), use_container_width=True, hide_index=True)

    col3, col4 = st.columns(2)
    with col3:
        section_title("Hidden gems", "Lower lifetime citations but high recent share")
        gems = cohort[(cohort["cited_by_count"] >= 1)].sort_values(["citation_momentum_index", "citations_365d"], ascending=False).head(12)
        cols = ["title", "first_author", "theme", "citations_365d", "cited_by_count", "citation_momentum_index"]
        st.dataframe(gems[cols], use_container_width=True, hide_index=True)
    with col4:
        section_title("Commissioning opportunities", "Themes with strongest recent citations per paper")
        th = explode_themes(cohort).groupby("theme_tag", as_index=False).agg(papers=("openalex_id", "nunique"), citations_365d=("citations_365d", "sum"))
        th["citations_365d_per_paper"] = (th["citations_365d"] / th["papers"].clip(lower=1)).round(2)
        th = th.sort_values(["citations_365d_per_paper", "papers"], ascending=False).head(12)
        st.dataframe(th, use_container_width=True, hide_index=True)


def report_page(snaps: pd.DataFrame) -> None:
    latest, _, latest_date, cohort = enrich_latest(snaps, 12, 36)
    page_header("Editorial Board Report", "One-page exportable summary", cohort, latest_date.date().isoformat())
    if latest.empty:
        st.warning("No papers found.")
        return
    metric_row_12_36(latest)
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        section_title("Top 5 papers")
        st.dataframe(prep_table(latest.sort_values("citations_365d", ascending=False).head(5)[["title", "first_author", "citations_365d", "cited_by_count", "theme"]]), use_container_width=True, hide_index=True)
    with col2:
        section_title("Top 5 themes")
        th = explode_themes(latest).groupby("theme_tag", as_index=False).agg(papers=("openalex_id", "nunique"), citations_365d=("citations_365d", "sum"))
        th["citations_365d_per_paper"] = (th["citations_365d"] / th["papers"].clip(lower=1)).round(2)
        st.dataframe(th.sort_values("citations_365d", ascending=False).head(5), use_container_width=True, hide_index=True)
    export = prep_table(latest.sort_values("citations_365d", ascending=False))
    st.download_button("Download full report data CSV", export.to_csv(index=False), "erjor_editorial_report_data.csv", "text/csv")
    st.caption("Use your browser's print command to save this page as PDF for now. A dedicated PDF export can be added later.")


inject_css()
sidebar_logo()

with st.sidebar:
    page = st.radio(
        "Navigation",
        [
            "1. Citation Performance\n12–36 Months",
            "2. New Papers\n0–12 Months",
            "3. Topic Momentum",
            "4. Editorial Intelligence",
            "5. Editorial Board Report",
        ],
        label_visibility="collapsed",
    )
    st.markdown("---")
    st.markdown("### Data refresh")
    mailto = st.text_input("OpenAlex mailto", value=DEFAULT_MAILTO)
    auto_refresh = st.checkbox("Auto-fetch if empty / stale", value=True)
    manual_refresh = st.button("Fetch latest data now", type="primary")
    st.caption("The app fetches ERJOR papers published 0–36 months ago.")
    st.markdown(
        """
        <div class="sidebar-footer">
          <strong>ERJ OPEN RESEARCH</strong><br/>
          Editorial citation intelligence using OpenAlex.<br/><br/>
          <span style="opacity:.9">Citations may differ from Google Scholar.</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

if manual_refresh or (auto_refresh and not snapshot_exists_for_today(DB_PATH)):
    try:
        fetched = fetch_latest_data(DB_PATH, mailto.strip() or DEFAULT_MAILTO)
        st.success(f"Fetched {fetched:,} ERJOR works from OpenAlex.")
        load_data.clear()
    except Exception as exc:
        st.error(f"Could not fetch OpenAlex data: {exc}")

works, snaps = load_data(str(DB_PATH))
if snaps.empty:
    page_header("ERJOR Editorial Intelligence", "No data loaded yet", "0–36 month ERJOR publication window", None)
    st.warning("No citation data is available yet. Click **Fetch latest data now** in the sidebar. On GitHub, the included workflow can refresh the data daily.")
    st.stop()

if page.startswith("1."):
    citation_performance(snaps)
elif page.startswith("2."):
    new_papers(snaps)
elif page.startswith("3."):
    topic_momentum(snaps)
elif page.startswith("4."):
    editorial_intelligence(snaps)
else:
    report_page(snaps)
