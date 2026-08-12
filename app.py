#!/usr/bin/env python3
"""
ERJOR Citation Analysis - Streamlit app.

Pulls ERJ Open Research citable items from OpenAlex (or accepts a Web of
Science export), rebuilds JCR-style citation windows, applies the agreed
thematic and methodological coding frame, and produces the tables and charts
for the editorial meeting.

The coding rules live in classify.py and the OpenAlex logic in
fetch_openalex.py - this file is presentation only, so the codebook stays a
single source of truth for both the app and the command line.
"""

import io
import math
from datetime import date

import altair as alt
import pandas as pd
import streamlit as st

import classify as C
import fetch_openalex as F

st.set_page_config(page_title="ERJOR Citation Analysis",
                   page_icon="\U0001F4CA", layout="wide")

WOS_2024 = {"items": 515, "zero": 74, "one": 103, "median": 3, "max": 60}



# ---------------------------------------------------------------------------
# Small statistics helpers (kept dependency-free)
# ---------------------------------------------------------------------------

def _norm_cdf(z):
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def two_proportion_test(x1, n1, x2, n2):
    """Compare two independent proportions. Returns (diff_pts, ci_lo, ci_hi, p)."""
    if n1 == 0 or n2 == 0:
        return (float("nan"),) * 4
    p1, p2 = x1 / n1, x2 / n2
    diff = p2 - p1
    se = math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    lo, hi = diff - 1.96 * se, diff + 1.96 * se
    pool = (x1 + x2) / (n1 + n2)
    se0 = math.sqrt(pool * (1 - pool) * (1 / n1 + 1 / n2))
    p = 2 * (1 - _norm_cdf(abs(diff) / se0)) if se0 > 0 else float("nan")
    return diff * 100, lo * 100, hi * 100, p


def mcnemar_exact(b, c):
    """Exact paired test on discordant pairs b and c."""
    n = b + c
    if n == 0:
        return float("nan")
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def fmt_p(p):
    if p != p:
        return "n/a"
    return "<0.001" if p < 0.001 else f"{p:.3f}"


# ---------------------------------------------------------------------------
# Data acquisition
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False, ttl=60 * 60 * 24)
def load_openalex(year_from: int, year_to: int, mailto: str) -> pd.DataFrame:
    src = F.find_source(mailto)
    works = F.fetch_works(src, year_from, year_to, mailto)
    return F.flatten(works)


@st.cache_data(show_spinner=False)
def code_papers(df: pd.DataFrame) -> pd.DataFrame:
    """Apply the theme and methodology codebooks."""
    d = df.copy()
    d["clean_title"] = d["Item Title"].map(C.normalise)

    th = d["clean_title"].map(lambda t: C.classify(t, C.THEMES))
    me = d["clean_title"].map(lambda t: C.classify(t, C.METHODS))

    d["Theme"] = [r[0] for r in th]
    d["Theme_all_matches"] = [r[1] for r in th]
    d["Theme_rule_hits"] = [r[2] for r in th]
    d["Methodology"] = [r[0] for r in me]
    d["Methodology_all_matches"] = [r[1] for r in me]
    d["Methodology_rule_hits"] = [r[2] for r in me]

    art = d["Document Type"].astype(str).str.strip().eq("Article")
    unc = d["Methodology"].eq("Other / Unclassified")
    d.loc[art & unc, "Methodology"] = "Original research - design not stated in title"

    is_rev = d["Document Type"].astype(str).str.strip().eq("Review")
    keep = d["Methodology"].isin(["Systematic Review / Meta-analysis",
                                  "Congress/Conference Report",
                                  "Guideline / Consensus / Delphi"])
    d.loc[is_rev & ~keep, "Methodology"] = "Narrative Review / Editorial"

    conf = lambda h: "High" if h >= 2 else ("Medium" if h == 1 else "Low")
    d["Theme_confidence"] = d["Theme_rule_hits"].map(conf)
    d["Methodology_confidence"] = d["Methodology_rule_hits"].map(conf)
    d["Needs_review"] = (d["Theme_confidence"].eq("Low")
                         | d["Methodology_confidence"].eq("Low"))

    d["Number of Citations"] = pd.to_numeric(d["Number of Citations"],
                                             errors="coerce")
    d["Zero_cited"] = d["Number of Citations"].eq(0)
    d["Low_cited_0_1"] = d["Number of Citations"].le(1)
    return d


def summarise(df: pd.DataFrame, col: str) -> pd.DataFrame:
    g = df.groupby(col, dropna=False).agg(
        Papers=("Number of Citations", "size"),
        Zero=("Zero_cited", "sum"),
        Low_0_1=("Low_cited_0_1", "sum"),
        Median=("Number of Citations", "median"),
        Mean=("Number of Citations", "mean"),
    ).reset_index()
    g["% zero"] = (g.Zero / g.Papers * 100).round(1)
    g["% 0-1"] = (g.Low_0_1 / g.Papers * 100).round(1)
    g["Mean"] = g.Mean.round(2)
    return g.sort_values("% zero", ascending=False)


def bar(df, x, y, title, min_n=1):
    d = df[df.Papers >= min_n]
    return (alt.Chart(d, title=title)
            .mark_bar(cornerRadiusEnd=3, color="#1F3864")
            .encode(
                x=alt.X(f"{x}:Q", title=x),
                y=alt.Y(f"{y}:N", sort="-x", title=None),
                tooltip=list(d.columns))
            .properties(height=max(220, 22 * len(d))))


def to_excel(sheets: dict) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xl:
        for name, d in sheets.items():
            d.to_excel(xl, sheet_name=name[:31], index=False)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

st.sidebar.title("ERJOR Citation Analysis")
st.sidebar.caption("Zero-citation and thematic analysis for the editorial "
                   "meeting")

source = st.sidebar.radio(
    "Data source",
    ["OpenAlex (live)", "Upload Web of Science export"],
    help="OpenAlex needs no login. Use the WoS option if you have a JCR "
         "citable-items export.")

st.sidebar.divider()

if source == "OpenAlex (live)":
    mailto = st.sidebar.text_input(
        "Your email",
        placeholder="you@example.com",
        help="Not stored. OpenAlex asks for it to put requests in their "
             "faster 'polite pool'.")
    this_jcr = st.sidebar.number_input(
        "Current JCR window", min_value=2018, max_value=date.today().year,
        value=2025,
        help="Citations received during this year, to papers published in "
             "the two preceding years.")
    prev_jcr = st.sidebar.number_input(
        "Comparison window", min_value=2017, max_value=date.today().year,
        value=2024)
    citable_only = st.sidebar.checkbox(
        "Citable items only (Articles + Reviews)", value=True,
        help="Matches the JCR denominator. Unticking includes editorials and "
             "letters, which inflates uncitedness.")
    go = st.sidebar.button("Fetch and analyse", type="primary",
                           use_container_width=True)
else:
    upload = st.sidebar.file_uploader("WoS export (.xlsx)", type=["xlsx"])
    go = upload is not None
    this_jcr = prev_jcr = None
    citable_only = True

st.sidebar.divider()
st.sidebar.caption("Coding rules are shared with the command-line scripts. "
                   "Edit classify.py to change them.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

st.title("ERJ Open Research \u2014 citation analysis")

if not go:
    st.info("Choose a data source in the sidebar to begin.")
    with st.expander("What this does", expanded=True):
        st.markdown("""
A journal impact factor counts citations received **during one year** by items
published in the **two preceding years**. OpenAlex records citations per year
for every paper, so that window can be rebuilt exactly rather than
approximated.

The app then applies a fixed rule-based coding frame \u2014 disease theme and study
methodology \u2014 so the same title always produces the same label, and every
assignment can be traced back to the rule that made it.

**Interpreting the numbers.** OpenAlex indexes more citing sources than Web of
Science, so it finds *fewer* uncited papers. Compare OpenAlex against OpenAlex,
never against a JCR figure from a previous year. The calibration panel shows
the size of that gap against the known 2024 Web of Science result.
        """)
    st.stop()

# --- load ---
if source == "OpenAlex (live)":
    if not mailto or "@" not in mailto:
        st.error("Please enter a valid email address in the sidebar. "
                 "OpenAlex requires it for API access.")
        st.stop()
    lo = min(prev_jcr, this_jcr) - 2
    hi = this_jcr - 1
    with st.spinner(f"Fetching {lo}\u2013{hi} from OpenAlex\u2026"):
        try:
            raw = load_openalex(lo, hi, mailto)
        except Exception as exc:
            st.error(f"OpenAlex request failed: {exc}")
            st.stop()
    if raw.empty:
        st.error("No works returned. Check the year range.")
        st.stop()

    cur = F.build_window(raw, this_jcr, citable_only)
    prev = F.build_window(raw, prev_jcr, citable_only)
    cur_l, prev_l = code_papers(cur), code_papers(prev)
    label_cur, label_prev = f"{this_jcr} window", f"{prev_jcr} window"
else:
    try:
        raw = C.load_wos(upload)
    except Exception as exc:
        st.error(f"Could not read that file: {exc}")
        st.stop()
    cur_l = code_papers(raw)
    prev_l = None
    label_cur = "Uploaded dataset"
    label_prev = None

# --- headline ---
st.subheader(label_cur)
c = cur_l["Number of Citations"]
cols = st.columns(5)
metrics = [
    ("Citable items", f"{len(cur_l)}", None),
    ("Zero citations", f"{int((c == 0).sum())}", f"{(c == 0).mean() * 100:.1f}%"),
    ("0\u20131 citations", f"{int((c <= 1).sum())}", f"{(c <= 1).mean() * 100:.1f}%"),
    ("Median", f"{c.median():.0f}", None),
    ("10+ citations", f"{int((c >= 10).sum())}", f"{(c >= 10).mean() * 100:.1f}%"),
]
for col, (lab, val, delta) in zip(cols, metrics):
    col.metric(lab, val, delta, delta_color="off")

if prev_l is not None:
    pc = prev_l["Number of Citations"]
    d_zero = (c == 0).mean() * 100 - (pc == 0).mean() * 100
    d_low = (c <= 1).mean() * 100 - (pc <= 1).mean() * 100
    st.caption(
        f"Against the {label_prev}: zero-citation rate "
        f"{'down' if d_zero < 0 else 'up'} {abs(d_zero):.1f} percentage points; "
        f"0\u20131 rate {'down' if d_low < 0 else 'up'} {abs(d_low):.1f} points. "
        f"Both windows come from the same database, so they are comparable.")

tabs = st.tabs(["Overview", "By theme", "By methodology", "Theme \u00d7 method",
                "Zero-cited papers", "Year on year", "Calibration", "Codebook"])

# --- overview ---
with tabs[0]:
    left, right = st.columns(2)
    with left:
        band = (cur_l["Number of Citations"]
                .clip(upper=15).value_counts().sort_index().reset_index())
        band.columns = ["Citations", "Papers"]
        st.altair_chart(
            alt.Chart(band, title="Citation distribution (15+ grouped)")
            .mark_bar(color="#1F3864")
            .encode(x=alt.X("Citations:O"), y="Papers:Q",
                    tooltip=["Citations", "Papers"]),
            use_container_width=True)
    with right:
        yr = summarise(cur_l, "Publication Year")
        st.dataframe(yr, use_container_width=True, hide_index=True)
    top = cur_l.nlargest(10, "Number of Citations")[
        ["Item Title", "Publication Year", "Theme", "Methodology",
         "Number of Citations"]]
    st.markdown("**Most cited in this window**")
    st.dataframe(top, use_container_width=True, hide_index=True)

# --- theme ---
with tabs[1]:
    min_n = st.slider("Minimum papers per theme", 1, 20, 8, key="tn")
    th = summarise(cur_l, "Theme")
    st.altair_chart(bar(th, "% zero", "Theme",
                        "Zero-citation rate by theme", min_n),
                    use_container_width=True)
    st.dataframe(th, use_container_width=True, hide_index=True)
    st.caption("Rate alone can mislead \u2014 a theme with four papers and one "
               "zero scores 25%. Read it against the Papers column.")

# --- methodology ---
with tabs[2]:
    min_m = st.slider("Minimum papers per method", 1, 20, 8, key="mn")
    me = summarise(cur_l, "Methodology")
    st.altair_chart(bar(me, "% zero", "Methodology",
                        "Zero-citation rate by methodology", min_m),
                    use_container_width=True)
    st.dataframe(me, use_container_width=True, hide_index=True)

# --- cross-tab ---
with tabs[3]:
    st.markdown("**Zero-cited / total papers, by theme and methodology**")
    n_ct = pd.crosstab(cur_l.Theme, cur_l.Methodology)
    z_ct = pd.crosstab(cur_l.Theme, cur_l.Methodology,
                       values=cur_l.Zero_cited, aggfunc="sum").fillna(0)
    floor = st.slider("Hide cells with fewer than N papers", 1, 10, 3)
    long = []
    for t in n_ct.index:
        for m in n_ct.columns:
            tot = int(n_ct.loc[t, m])
            if tot >= floor:
                long.append({"Theme": t, "Methodology": m, "Papers": tot,
                             "Zero": int(z_ct.loc[t, m]),
                             "% zero": round(z_ct.loc[t, m] / tot * 100, 1)})
    if long:
        ld = pd.DataFrame(long)
        st.altair_chart(
            alt.Chart(ld).mark_rect().encode(
                x=alt.X("Methodology:N", axis=alt.Axis(labelAngle=-40)),
                y=alt.Y("Theme:N", title=None),
                color=alt.Color("% zero:Q",
                                scale=alt.Scale(scheme="orangered")),
                tooltip=["Theme", "Methodology", "Papers", "Zero", "% zero"]
            ).properties(height=max(300, 20 * ld.Theme.nunique())),
            use_container_width=True)
        st.dataframe(ld.sort_values("% zero", ascending=False),
                     use_container_width=True, hide_index=True)
    else:
        st.info("No cells meet the minimum. Lower the threshold.")

# --- zero-cited ---
with tabs[4]:
    z = cur_l[cur_l.Zero_cited].copy()
    st.markdown(f"**{len(z)} papers with zero citations in this window**")
    st.caption("Theme and Methodology are editable. Correct anything "
               "misclassified, then download \u2014 send the file back and the "
               "rules can be updated so the fix persists next year.")
    show = z[["Item Title", "Publication Year", "Theme", "Methodology",
              "Theme_confidence", "Methodology_confidence"]]
    edited = st.data_editor(
        show, use_container_width=True, hide_index=True, num_rows="fixed",
        column_config={
            "Theme": st.column_config.SelectboxColumn(
                options=sorted({t for t, _ in C.THEMES} | {"Other / Unclassified"})),
            "Methodology": st.column_config.SelectboxColumn(
                options=sorted({m for m, _ in C.METHODS} |
                               {"Original research - design not stated in title",
                                "Other / Unclassified"})),
        })
    st.download_button("Download zero-cited papers (CSV)",
                       edited.to_csv(index=False).encode(),
                       "erjor_zero_cited_reviewed.csv", "text/csv")

# --- year on year ---
with tabs[5]:
    if prev_l is None:
        st.info("Year-on-year comparison needs the OpenAlex source, which "
                "builds both windows.")
    else:
        a = summarise(prev_l, "Theme")[["Theme", "Papers", "Zero", "% zero"]]
        b = summarise(cur_l, "Theme")[["Theme", "Papers", "Zero", "% zero"]]
        m = a.merge(b, on="Theme", how="outer",
                    suffixes=(f" {prev_jcr}", f" {this_jcr}")).fillna(0)
        m["Change (pts)"] = (m[f"% zero {this_jcr}"]
                             - m[f"% zero {prev_jcr}"]).round(1)
        st.markdown("**Movement in zero-citation rate by theme**")
        st.dataframe(m.sort_values("Change (pts)"),
                     use_container_width=True, hide_index=True)

        st.divider()
        st.markdown("### Age-matched cohort comparison")
        st.caption(
            "Each window contains a younger and an older cohort. Comparing "
            "like with like removes the citation-ageing effect, so a "
            "difference here reflects what was published rather than how long "
            "it has had to be cited.")

        pairs = [
            ("Younger cohort", prev_jcr - 1, this_jcr - 1),
            ("Older cohort", prev_jcr - 2, this_jcr - 2),
        ]
        rows = []
        for lab, y_old, y_new in pairs:
            a = prev_l[prev_l["Publication Year"] == y_old]
            b = cur_l[cur_l["Publication Year"] == y_new]
            if a.empty or b.empty:
                continue
            x1, n1 = int(a.Zero_cited.sum()), len(a)
            x2, n2 = int(b.Zero_cited.sum()), len(b)
            d, lo, hi, p = two_proportion_test(x1, n1, x2, n2)
            rows.append({
                "Cohort": lab,
                f"{y_old} papers (in {prev_jcr})": f"{x1}/{n1} "
                                                   f"({x1 / n1 * 100:.1f}%)",
                f"{y_new} papers (in {this_jcr})": f"{x2}/{n2} "
                                                   f"({x2 / n2 * 100:.1f}%)",
                "Change (pts)": f"{d:+.1f}",
                "95% CI": f"{lo:+.1f} to {hi:+.1f}",
                "p": fmt_p(p),
            })
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True,
                         hide_index=True)
            st.caption(
                "A confidence interval spanning zero means the data are also "
                "consistent with no change. With a few hundred papers per "
                "cohort, only fairly large shifts will be distinguishable "
                "from chance \u2014 worth saying out loud if the board reads a "
                "small movement as progress.")

        st.divider()
        st.markdown("### Unadjusted comparison (interpret with care)")
        za, na = int(prev_l.Zero_cited.sum()), len(prev_l)
        zb, nb = int(cur_l.Zero_cited.sum()), len(cur_l)
        u1, u2 = st.columns(2)
        u1.metric(f"{prev_jcr} window", f"{za / na * 100:.1f}%",
                  f"{za} of {na}", delta_color="off")
        u2.metric(f"{this_jcr} window", f"{zb / nb * 100:.1f}%",
                  f"{zb} of {nb}", delta_color="off")
        st.caption(
            "These two windows share a publication year, so they are not "
            "independent samples, and the cohorts differ in age. Use the "
            "age-matched table above for any claim about improvement.")

        overlap = sorted(set(prev_l["Publication Year"])
                         & set(cur_l["Publication Year"]))
        if overlap:
            yr = overlap[0]
            p = prev_l[prev_l["Publication Year"] == yr][["UT", "Item Title",
                                                          "Number of Citations",
                                                          "Theme"]]
            q = cur_l[cur_l["Publication Year"] == yr][["UT",
                                                        "Number of Citations"]]
            j = p.merge(q, on="UT", suffixes=(f"_{prev_jcr}", f"_{this_jcr}"))
            was_zero = j[j[f"Number of Citations_{prev_jcr}"] == 0]
            still = was_zero[was_zero[f"Number of Citations_{this_jcr}"] == 0]
            st.divider()
            st.markdown(f"**Catch-up analysis \u2014 {yr} papers, "
                        f"tracked across both windows**")
            k1, k2, k3 = st.columns(3)
            k1.metric(f"Zero in {prev_jcr}", len(was_zero))
            k2.metric(f"Still zero in {this_jcr}", len(still))
            if len(was_zero):
                k3.metric("Picked up citations",
                          f"{(1 - len(still) / len(was_zero)) * 100:.0f}%")
            gained = len(was_zero) - len(still)
            lost = int(((j[f"Number of Citations_{prev_jcr}"] > 0)
                        & (j[f"Number of Citations_{this_jcr}"] == 0)).sum())
            pv = mcnemar_exact(gained, lost)
            st.caption(
                f"Same papers, matched on identifier: {gained} moved off zero "
                f"while {lost} fell back to zero (paired exact test "
                f"p={fmt_p(pv)}). Papers that stay at zero are persistently "
                "uncited rather than merely slow \u2014 that distinction is what "
                "makes this actionable. Note this is expected to improve on "
                "ageing alone, so treat it as a measure of how much "
                "uncitedness is temporary, not as evidence of editorial "
                "change.")
            st.dataframe(still[["Item Title", "Theme"]],
                         use_container_width=True, hide_index=True)

# --- calibration ---
with tabs[6]:
    st.markdown("**Sanity check against Web of Science**")
    if source == "OpenAlex (live)" and 2024 in (this_jcr, prev_jcr):
        w = cur_l if this_jcr == 2024 else prev_l
        wc = w["Number of Citations"]
        comp = pd.DataFrame({
            "Measure": ["Citable items", "Zero citations", "One citation",
                        "Median citations", "Max citations"],
            "Web of Science (JCR 2024)": [WOS_2024["items"], WOS_2024["zero"],
                                          WOS_2024["one"], WOS_2024["median"],
                                          WOS_2024["max"]],
            "OpenAlex (this app)": [len(w), int((wc == 0).sum()),
                                    int((wc == 1).sum()),
                                    int(wc.median()), int(wc.max())],
        })
        st.dataframe(comp, use_container_width=True, hide_index=True)
        st.caption(
            "OpenAlex should find somewhat fewer uncited papers, because it "
            "counts citations from a wider set of sources. Its document typing "
            "is also algorithmic, so the denominator will not match exactly. "
            "A large discrepancy \u2014 say the item count differing by more than "
            "20% \u2014 means something is wrong and the numbers should not be "
            "presented.")
    else:
        st.info("Set one of the windows to 2024 to compare against the known "
                "Web of Science result.")

# --- codebook ---
with tabs[7]:
    st.caption("Rules are applied in the order shown. A paper scores one point "
               "per distinct pattern matched; highest score wins, ties broken "
               "by position in this list.")
    for name, book in (("Disease themes", C.THEMES),
                       ("Methodologies", C.METHODS)):
        st.markdown(f"**{name}**")
        st.dataframe(pd.DataFrame([
            {"Priority": i, "Label": lab,
             "Patterns": "; ".join(p.replace("\\b", "") for p in pats)}
            for i, (lab, pats) in enumerate(book, 1)]),
            use_container_width=True, hide_index=True)

# --- downloads ---
st.divider()
d1, d2 = st.columns(2)
d1.download_button("Download labelled dataset (CSV)",
                   cur_l.to_csv(index=False).encode(),
                   f"erjor_labelled_{label_cur.replace(' ', '_')}.csv",
                   "text/csv", use_container_width=True)
sheets = {"Labelled data": cur_l, "By theme": summarise(cur_l, "Theme"),
          "By methodology": summarise(cur_l, "Methodology"),
          "Zero-cited": cur_l[cur_l.Zero_cited]}
if prev_l is not None:
    sheets["Previous window"] = prev_l
d2.download_button("Download full workbook (Excel)", to_excel(sheets),
                   "ERJOR_Citation_Analysis.xlsx",
                   "application/vnd.openxmlformats-officedocument."
                   "spreadsheetml.sheet", use_container_width=True)
