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
            --ers-navy: #002b5c;
            --ers-blue: #004b93;
            --ers-mid-blue: #0067b1;
            --ers-red: #e30613;
            --ers-teal: #008c95;
            --ers-light: #f5f8fc;
            --ers-border: #d8dee9;
            --ers-text: #101828;
        }}
        .stApp {{
            background: radial-gradient(circle at top right, rgba(0,75,147,.08), transparent 30%), #ffffff;
        }}
        .block-container {{ padding-top: 1.25rem; padding-bottom: 2rem; max-width: 1600px; }}
        section[data-testid="stSidebar"] {{
            background:
              radial-gradient(circle at 15% 96%, rgba(255,255,255,.12) 0 2px, transparent 2px) 0 0/18px 18px,
              linear-gradient(180deg, #003b71 0%, #004b93 45%, #002b5c 100%);
            box-shadow: 8px 0 30px rgba(0,43,92,.14);
        }}
        section[data-testid="stSidebar"] * {{ color: white !important; }}
        section[data-testid="stSidebar"] .stRadio > label {{ display:none; }}
        section[data-testid="stSidebar"] div[role="radiogroup"] label {{
            padding: .85rem .8rem;
            border-radius: 12px;
            margin: .18rem 0;
            border: 1px solid rgba(255,255,255,.08);
        }}
        section[data-testid="stSidebar"] div[role="radiogroup"] label:hover {{
            background: rgba(255,255,255,.10);
        }}
        .ers-sidebar-brand {{ padding: 18px 8px 24px 0; }}
        .ers-logo-row {{ display:flex; gap:14px; align-items:flex-start; }}
        .ers-mark {{
            width:64px; height:64px; border-radius:50%;
            background: var(--ers-red);
            box-shadow: 0 8px 24px rgba(0,0,0,.22);
            position:relative; flex: 0 0 64px;
        }}
        .ers-mark:before {{
            content:""; position:absolute; inset:13px;
            background:
              radial-gradient(circle, #fff 0 2px, transparent 2.5px) 0 0/9px 9px;
            opacity:.95; border-radius:50%;
        }}
        .ers-wordmark .ers {{ font-size:2.35rem; font-weight:900; letter-spacing:.02em; line-height:.86; }}
        .ers-wordmark .society {{ font-size:.78rem; font-weight:800; line-height:1.15; margin-top:6px; letter-spacing:.04em; }}
        .journal-lockup {{ margin-top:26px; }}
        .journal-lockup .journal-title {{ font-size:1.15rem; font-weight:900; letter-spacing:.01em; }}
        .journal-lockup .journal-sub {{ margin-top:7px; font-size:.84rem; line-height:1.4; opacity:.96; }}
        .sidebar-footer {{
            margin-top:32px; padding-top:20px; border-top:1px solid rgba(255,255,255,.35);
            font-size:.82rem; line-height:1.45; opacity:.95;
        }}
        .ers-topbar {{
            display:flex; justify-content:space-between; align-items:flex-start; gap:24px;
            border-bottom:1px solid #e4e9f2; padding-bottom:14px; margin-bottom:18px;
        }}
        .ers-product {{ font-size:1.45rem; font-weight:900; letter-spacing:.04em; color:var(--ers-blue); }}
        .ers-product span {{ color:var(--ers-red); }}
        .ers-right-lockup {{
            color:var(--ers-blue); font-weight:850; letter-spacing:.03em; line-height:1.15; text-align:left;
            display:flex; align-items:flex-start; gap:22px;
        }}
        .ers-right-lockup .open {{ color:var(--ers-red); margin-top:6px; }}
        .ers-lungs {{ width:76px; height:54px; position:relative; margin-top:2px; }}
        .ers-lungs:before, .ers-lungs:after {{ content:""; position:absolute; width:28px; height:48px; border-radius: 60% 60% 45% 45%; top:2px; }}
        .ers-lungs:before {{ left:5px; border-left:8px dotted var(--ers-blue); border-top:8px dotted var(--ers-blue); transform:rotate(16deg); }}
        .ers-lungs:after {{ right:5px; border-right:8px dotted var(--ers-red); border-top:8px dotted var(--ers-red); transform:rotate(-16deg); }}
        .erj-header {{ margin-bottom: 1rem; }}
        .erj-title h1 {{ color: var(--ers-navy); font-size:2.05rem; font-weight:900; margin:0; line-height:1.1; }}
        .erj-title p {{ color:#455a7a; font-size:1.1rem; margin:.45rem 0 0 0; }}
        .erj-subnote {{ color:#53637a; font-size:.88rem; margin:.8rem 0 0 0; }}
        div[data-testid="stMetric"] {{
            background:#fff; border:1px solid var(--ers-border); border-radius:14px;
            padding:18px 18px 14px 18px; box-shadow:0 2px 14px rgba(16,24,40,.045);
            min-height:142px; position:relative; overflow:hidden;
        }}
        div[data-testid="stMetric"]:before {{
            content:""; position:absolute; left:0; top:0; bottom:0; width:5px; background:var(--ers-blue);
        }}
        div[data-testid="stMetric"]:nth-of-type(3):before {{ background:var(--ers-red); }}
        div[data-testid="stMetricLabel"] p {{
            color: var(--ers-blue) !important; font-weight:900 !important; text-transform:uppercase;
            font-size:.75rem !important; letter-spacing:.02em;
        }}
        div[data-testid="stMetricValue"] {{ color:var(--ers-text); font-weight:900; }}
        div[data-testid="stMetricDelta"] {{ color:var(--ers-red) !important; }}
        .section-card {{
            background:#fff; border:1px solid var(--ers-border); border-radius:14px;
            padding:16px 18px; box-shadow:0 2px 14px rgba(16,24,40,.045); margin-bottom:14px;
        }}
        .section-card h3, h3 {{ color:var(--ers-blue) !important; text-transform:uppercase; font-size:.9rem !important; letter-spacing:.02em; }}
        .pill {{ display:inline-block; background:#eef4ff; color:var(--ers-blue); border:1px solid #c7d7fe; border-radius:999px; padding:3px 10px; margin:2px 4px 2px 0; font-size:.78rem; font-weight:700; }}
        div[data-testid="stDataFrame"] {{ border:1px solid var(--ers-border); border-radius:12px; }}
        .stDownloadButton button, button[kind="primary"] {{ background:var(--ers-blue) !important; color:white !important; border:0 !important; }}
        .stButton button {{ border-radius:10px; }}
        </style>
        """,
        unsafe_allow_html=True,
    )

def sidebar_logo() -> None:
    st.sidebar.markdown(
        """
        <div class="ers-sidebar-brand">
          <div class="ers-logo-row">
            <div class="ers-mark"></div>
            <div class="ers-wordmark">
              <div class="ers">ERS</div>
              <div class="society">EUROPEAN<br/>RESPIRATORY<br/>SOCIETY</div>
            </div>
          </div>
          <div class="journal-lockup">
            <div class="journal-title">ERJ OPEN RESEARCH</div>
            <div class="journal-sub">Advancing open respiratory<br/>science for better health</div>
          </div>
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
        <div class="ers-topbar">
          <div class="ers-product">ERJ <span>OPEN RESEARCH</span></div>
          <div class="ers-right-lockup">
            <div>EUROPEAN RESPIRATORY<br/>JOURNAL<div class="open">OPEN RESEARCH</div></div>
            <div class="ers-lungs"></div>
          </div>
        </div>
        <div class="erj-header">
          <div class="erj-title">
            <h1>{title}</h1>
            <p>{subtitle}</p>
            <div class="erj-subnote">ⓘ {details_text}</div>
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


def fetch_latest_data(db_path: Path, mailto: str, min_age_months: int = 0, max_age_months: int = 60) -> int:
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
        fig = px.scatter(latest, x="cited_by_count", y="citations_365d", hover_name="title", hover_data=["first_author", "article_type"], )
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



EXCLUDED_CITABLE_PATTERNS = [
    "editorial", "letter", "correspondence", "research letter", "reply", "response to",
    "correction", "erratum", "corrigendum", "retraction", "news", "obituary", "commentary",
]
INCLUDED_CITABLE_PATTERNS = [
    "original research", "research article", "article", "review", "systematic review", "meta-analysis", "meta analysis",
    "methods", "clinical trial",
]


def citable_decision(row: pd.Series) -> tuple[bool, str]:
    """Estimate whether a work should be counted in the Impact Factor denominator.

    This is an OpenAlex/Crossref-based approximation of the Web of Science citable-item
    denominator. It intentionally excludes editorials, letters, correspondence and
    research letters where the metadata or title suggests those article types.
    """
    title = str(row.get("title") or "").strip().lower()
    article_type = str(row.get("article_type") or "").strip().lower()
    work_type = str(row.get("work_type") or "").strip().lower()
    text = f" {title} {article_type} {work_type} "

    for term in EXCLUDED_CITABLE_PATTERNS:
        if term in text or title.startswith(term + ":") or title.startswith(term + " "):
            return False, f"Excluded: {term}"

    if "review" in article_type or "review" in work_type or "systematic review" in title or "meta-analysis" in title or "meta analysis" in title:
        return True, "Included: review"
    if "original" in article_type or "article" in work_type or "journal-article" in work_type:
        return True, "Included: article/research"

    for term in INCLUDED_CITABLE_PATTERNS:
        if term in text:
            return True, f"Included: {term}"
    return False, "Excluded: ambiguous/non-citable"


def add_citable_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if out.empty:
        out["is_citable"] = []
        out["citable_reason"] = []
        return out
    decisions = out.apply(citable_decision, axis=1)
    out["is_citable"] = decisions.apply(lambda x: x[0])
    out["citable_reason"] = decisions.apply(lambda x: x[1])
    return out


def latest_all_works(snaps: pd.DataFrame) -> tuple[pd.DataFrame, pd.Timestamp]:
    latest_date = snaps["snapshot_date"].max()
    latest = snaps[snaps["snapshot_date"] == latest_date].copy()
    latest["themes"] = latest.apply(tag_themes, axis=1)
    latest["theme"] = latest["themes"].apply(lambda x: "; ".join(x))
    return latest, latest_date


def eif_for_year(df: pd.DataFrame, year: int) -> tuple[pd.DataFrame, pd.DataFrame, int, float]:
    start_pub = pd.Timestamp(year=year-2, month=1, day=1)
    end_pub = pd.Timestamp(year=year-1, month=12, day=31)
    window = df[(df["publication_date"] >= start_pub) & (df["publication_date"] <= end_pub)].copy()
    window = add_citable_columns(window)
    citable = window[window["is_citable"]].copy()
    y0 = dt.date(year, 1, 1)
    y1 = dt.date(year + 1, 1, 1)
    citable["jif_year_citations"] = citable.apply(lambda r: citation_count_between(r, y0, y1), axis=1)
    numerator = int(citable["jif_year_citations"].sum()) if not citable.empty else 0
    denominator = int(citable["openalex_id"].nunique()) if not citable.empty else 0
    eif = numerator / denominator if denominator else 0.0
    return window, citable, numerator, eif


def impact_factor_page(snaps: pd.DataFrame) -> None:
    latest, latest_date = latest_all_works(snaps)
    default_year = dt.date.today().year
    page_header(
        "Estimated Impact Factor",
        "OpenAlex-based live estimate using a Web of Science-style two-year citation window",
        f"JIF denominator window updates with selected year",
        latest_date.date().isoformat(),
    )
    st.info(
        "This is an **estimate**, not the official Clarivate Journal Impact Factor. "
        "The denominator excludes editorials, letters, correspondence, research letters, corrections and similar items where identifiable."
    )

    available_years = sorted(set(int(y) for y in latest["publication_year"].dropna().astype(int).unique()))
    min_year = max(min(available_years) + 2, default_year - 4) if available_years else default_year
    year_options = list(range(min_year, default_year + 1))
    selected_year = st.selectbox("Impact Factor year", year_options[::-1], index=0)

    window, citable, numerator, eif = eif_for_year(latest, int(selected_year))
    denominator = int(citable["openalex_id"].nunique()) if not citable.empty else 0
    excluded_count = int(window[~window.get("is_citable", False)].openalex_id.nunique()) if not window.empty and "is_citable" in window else 0
    today = dt.date.today()
    days_elapsed = (today - dt.date(selected_year, 1, 1)).days + 1 if selected_year == today.year else 365
    days_in_year = 366 if dt.date(selected_year, 12, 31).timetuple().tm_yday == 366 else 365
    projected_numerator = int(round(numerator * days_in_year / max(days_elapsed, 1))) if selected_year == today.year else numerator
    projected_eif = projected_numerator / denominator if denominator else 0.0

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Estimated IF", f"{eif:.2f}")
    c2.metric("Projected year-end IF", f"{projected_eif:.2f}")
    c3.metric("Citations in IF year", f"{numerator:,}")
    c4.metric("Citable items", f"{denominator:,}")
    c5.metric("Excluded items", f"{excluded_count:,}")
    c6.metric("Publication window", f"{selected_year-2}–{selected_year-1}")

    col1, col2 = st.columns([1.15, 1])
    with col1:
        section_title("Estimated IF by year", "OpenAlex-based annual estimates where data are available")
        rows = []
        for y in year_options:
            w, c, n, val = eif_for_year(latest, y)
            rows.append({
                "year": y,
                "estimated_if": round(val, 3),
                "citations_to_previous_2y": n,
                "citable_items": int(c["openalex_id"].nunique()) if not c.empty else 0,
                "publication_window": f"{y-2}-{y-1}",
            })
        hist = pd.DataFrame(rows)
        fig = px.line(hist, x="year", y="estimated_if", markers=True, hover_data=["citations_to_previous_2y", "citable_items", "publication_window"])
        fig.update_traces(line_color=ERJ_RED)
        st.plotly_chart(chart_layout(fig), use_container_width=True)
        st.dataframe(hist.sort_values("year", ascending=False), use_container_width=True, hide_index=True)
    with col2:
        section_title("Numerator contributors", "Papers driving the estimated Impact Factor")
        if citable.empty:
            st.warning("No citable items found for this denominator window.")
        else:
            top = citable.sort_values("jif_year_citations", ascending=False).head(15)
            fig = px.bar(top, x="jif_year_citations", y="title", orientation="h", hover_data=["first_author", "article_type", "publication_date"])
            fig.update_traces(marker_color=ERJ_BLUE)
            fig.update_layout(yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(chart_layout(fig), use_container_width=True)

    section_title("Citable items audit", "Review inclusion/exclusion decisions for the denominator")
    if window.empty:
        st.warning("No works found in the selected two-year publication window. Fetching a wider OpenAlex window may be needed.")
    else:
        audit = window.copy()
        if "jif_year_citations" not in audit:
            audit["jif_year_citations"] = audit.apply(lambda r: citation_count_between(r, dt.date(selected_year, 1, 1), dt.date(selected_year + 1, 1, 1)), axis=1)
        audit = prep_table(audit[[
            "title", "first_author", "publication_date", "article_type", "work_type",
            "is_citable", "citable_reason", "jif_year_citations", "cited_by_count", "doi", "landing_page_url"
        ]].sort_values(["is_citable", "jif_year_citations"], ascending=[False, False]))
        st.dataframe(audit, use_container_width=True, hide_index=True)
        st.download_button(
            "Download citable items audit CSV",
            audit.to_csv(index=False),
            f"erjor_estimated_if_{selected_year}_audit.csv",
            "text/csv",
        )

    section_title("What-if calculator")
    wc1, wc2, wc3 = st.columns(3)
    extra_citations = wc1.number_input("Extra citations in IF year", min_value=0, value=0, step=1)
    add_items = wc2.number_input("Additional citable items", min_value=0, value=0, step=1)
    remove_items = wc3.number_input("Citable items to exclude", min_value=0, value=0, step=1)
    adjusted_denominator = max(denominator + int(add_items) - int(remove_items), 1)
    adjusted_eif = (numerator + int(extra_citations)) / adjusted_denominator
    st.metric("Adjusted estimated IF", f"{adjusted_eif:.2f}", delta=f"{adjusted_eif - eif:+.2f} vs current estimate")

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
            "5. Estimated Impact Factor",
            "6. Editorial Board Report",
        ],
        label_visibility="collapsed",
    )
    st.markdown("---")
    st.markdown("### Data refresh")
    mailto = st.text_input("OpenAlex mailto", value=DEFAULT_MAILTO)
    auto_refresh = st.checkbox("Auto-fetch if empty / stale", value=True)
    manual_refresh = st.button("Fetch latest data now", type="primary")
    st.caption("The app fetches ERJOR papers published 0–60 months ago to support citation and estimated Impact Factor windows.")
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
elif page.startswith("5."):
    impact_factor_page(snaps)
else:
    report_page(snaps)
