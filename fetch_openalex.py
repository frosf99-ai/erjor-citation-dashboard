#!/usr/bin/env python3
"""
Pull ERJ Open Research citable items from OpenAlex and rebuild JCR-style
citation windows.

WHY THIS WORKS
--------------
A journal impact factor window counts citations received *during a single
year* by items published in the two preceding years. OpenAlex exposes exactly
that via each work's `counts_by_year` field, so the metric can be rebuilt
rather than approximated:

    2024 window  = citations during 2024 to items published 2022 + 2023
    2025 window  = citations during 2025 to items published 2023 + 2024

The 2024 window reproduces the Web of Science export you already have, which
gives you a direct calibration of how far the two databases diverge.

USAGE
-----
    pip install requests pandas openpyxl
    python fetch_openalex.py --mailto you@example.com

OUTPUT
------
    openalex_window_2024.csv   pub 2022-2023, citations during 2024
    openalex_window_2025.csv   pub 2023-2024, citations during 2025
    openalex_raw_works.csv     every work retrieved, all years
    calibration.txt            OpenAlex vs Web of Science comparison

Both window files use the same column names as the WoS export, so classify.py
runs on them unmodified.

No API key or institutional access is required.
"""

import argparse
import sys
import time

import pandas as pd

try:
    import requests
except ImportError:
    sys.exit("Please run: pip install requests pandas openpyxl")

API = "https://api.openalex.org"
ISSN = "2312-0541"          # ERJ Open Research

# Only these fields are requested, which keeps responses small and fast.
SELECT = ",".join([
    "id", "doi", "title", "publication_year", "publication_date",
    "type", "cited_by_count", "counts_by_year", "authorships",
    "primary_topic", "open_access", "abstract_inverted_index", "biblio",
])


def get(url, params, tries=4):
    """GET with simple exponential backoff."""
    for attempt in range(tries):
        try:
            r = requests.get(url, params=params, timeout=60)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (429, 500, 502, 503):
                time.sleep(2 ** attempt)
                continue
            r.raise_for_status()
        except requests.RequestException as exc:
            if attempt == tries - 1:
                raise
            print(f"    retry after error: {exc}")
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Failed after {tries} attempts: {url}")


def find_source(mailto):
    """Resolve the journal's OpenAlex source ID from its ISSN."""
    data = get(f"{API}/sources", {
        "filter": f"issn:{ISSN}",
        "select": "id,display_name,issn_l,works_count",
        "mailto": mailto,
    })
    results = data.get("results", [])
    if not results:
        sys.exit(f"No OpenAlex source found for ISSN {ISSN}")
    src = results[0]
    sid = src["id"].rsplit("/", 1)[-1]
    print(f"Source: {src['display_name']}  ({sid}, "
          f"{src.get('works_count', '?')} works indexed)")
    return sid


def fetch_works(source_id, year_from, year_to, mailto):
    """Cursor-paginate every work in the given publication-year range."""
    works, cursor, page = [], "*", 0
    while cursor:
        page += 1
        data = get(f"{API}/works", {
            "filter": (f"primary_location.source.id:{source_id},"
                       f"publication_year:{year_from}-{year_to}"),
            "select": SELECT,
            "per-page": 200,
            "cursor": cursor,
            "mailto": mailto,
        })
        batch = data.get("results", [])
        works.extend(batch)
        total = data.get("meta", {}).get("count", 0)
        print(f"  page {page}: {len(works)}/{total}")
        cursor = data.get("meta", {}).get("next_cursor")
        if not batch:
            break
        time.sleep(0.15)          # stay well inside the rate limit
    return works


def rebuild_abstract(inv):
    """OpenAlex stores abstracts as {word: [positions]}. Reassemble the text.

    Presence or absence of an abstract is often a good proxy for content type:
    original articles carry one, research letters and correspondence usually
    do not. Validate that against a known citable-item list before relying on
    it - coverage depends on what the publisher deposited with Crossref.
    """
    if not inv:
        return ""
    pos = {}
    for word, places in inv.items():
        for p in places:
            pos[p] = word
    if not pos:
        return ""
    return " ".join(pos[i] for i in sorted(pos))


def flatten(works):
    """One row per work, with citations-per-year expanded into columns."""
    rows = []
    for w in works:
        by_year = {c["year"]: c["cited_by_count"]
                   for c in (w.get("counts_by_year") or [])}
        auths = w.get("authorships") or []
        names = [a.get("author", {}).get("display_name", "") for a in auths]
        countries = sorted({c for a in auths
                            for c in (a.get("countries") or [])})
        topic = (w.get("primary_topic") or {}).get("display_name", "")
        abstract = rebuild_abstract(w.get("abstract_inverted_index"))
        bib = w.get("biblio") or {}

        def _page(v):
            try:
                return int(str(v).strip())
            except (TypeError, ValueError):
                return None

        fp, lp = _page(bib.get("first_page")), _page(bib.get("last_page"))
        n_pages = (lp - fp + 1) if (fp is not None and lp is not None
                                    and lp >= fp) else None
        rows.append({
            "openalex_id": w["id"].rsplit("/", 1)[-1],
            "doi": (w.get("doi") or "").replace("https://doi.org/", ""),
            "Item Title": w.get("title") or "",
            "Authors": ";".join(names[:10]),
            "n_authors": len(names),
            "countries": ";".join(countries),
            "Publication Year": w.get("publication_year"),
            "publication_date": w.get("publication_date"),
            "openalex_type": w.get("type"),
            "primary_topic": topic,
            "is_oa": (w.get("open_access") or {}).get("is_oa"),
            "abstract": abstract,
            "has_abstract": bool(abstract),
            "abstract_words": len(abstract.split()) if abstract else 0,
            "first_page": bib.get("first_page"),
            "last_page": bib.get("last_page"),
            "n_pages": n_pages,
            "cited_by_count_total": w.get("cited_by_count", 0),
            "cites_2022": by_year.get(2022, 0),
            "cites_2023": by_year.get(2023, 0),
            "cites_2024": by_year.get(2024, 0),
            "cites_2025": by_year.get(2025, 0),
            "cites_2026": by_year.get(2026, 0),
        })
    return pd.DataFrame(rows)


# OpenAlex types that correspond to JCR "citable items"
CITABLE = {"article", "review"}

TYPE_MAP = {"article": "Article", "review": "Review"}


def build_window(df, jcr_year, citable_only=True):
    """Items published in the two preceding years, cited during jcr_year."""
    pub_years = [jcr_year - 2, jcr_year - 1]
    w = df[df["Publication Year"].isin(pub_years)].copy()
    if citable_only:
        w = w[w["openalex_type"].isin(CITABLE)]
    w["Number of Citations"] = w[f"cites_{jcr_year}"]
    w["Document Type"] = w["openalex_type"].map(TYPE_MAP).fillna("Other")
    w["UT"] = w["openalex_id"]
    w["Source Title"] = "ERJ OPEN RESEARCH"
    w["JCR_window"] = jcr_year
    return w.sort_values(["Publication Year", "Number of Citations"],
                         ascending=[True, False])


def describe(w, label):
    n = len(w)
    c = w["Number of Citations"]
    return (f"{label}\n"
            f"  citable items      : {n}\n"
            f"  zero citations     : {int((c == 0).sum())} "
            f"({(c == 0).mean() * 100:.1f}%)\n"
            f"  one citation       : {int((c == 1).sum())} "
            f"({(c == 1).mean() * 100:.1f}%)\n"
            f"  0-1 citations      : {int((c <= 1).sum())} "
            f"({(c <= 1).mean() * 100:.1f}%)\n"
            f"  10+ citations      : {int((c >= 10).sum())}\n"
            f"  median / mean / max: {c.median():.0f} / {c.mean():.2f} / "
            f"{int(c.max())}\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mailto", required=True,
                    help="Your email. Puts requests in OpenAlex's faster "
                         "'polite pool'. Not stored or published.")
    ap.add_argument("--from-year", type=int, default=2022)
    ap.add_argument("--to-year", type=int, default=2024)
    ap.add_argument("--include-noncitable", action="store_true",
                    help="Keep editorials, letters and errata as well as "
                         "articles and reviews")
    args = ap.parse_args()

    src = find_source(args.mailto)

    print(f"\nFetching works {args.from_year}-{args.to_year} ...")
    works = fetch_works(src, args.from_year, args.to_year, args.mailto)
    df = flatten(works)
    df.to_csv("openalex_raw_works.csv", index=False)
    print(f"\nRetrieved {len(df)} works -> openalex_raw_works.csv")
    print("\nBy publication year and type:")
    print(pd.crosstab(df["Publication Year"], df["openalex_type"]).to_string())

    print("\nAbstract coverage (proxy for content type):")
    cov = df.groupby("Publication Year")["has_abstract"].agg(["sum", "size"])
    cov["% with abstract"] = (cov["sum"] / cov["size"] * 100).round(1)
    print(cov.to_string())
    print("  If coverage is near 100% or near 0% for every year, abstracts")
    print("  carry no information about content type here. A split roughly")
    print("  matching the citable-item share means the proxy is usable.")

    citable = not args.include_noncitable
    w24 = build_window(df, 2024, citable)
    w25 = build_window(df, 2025, citable)
    w24.to_csv("openalex_window_2024.csv", index=False)
    w25.to_csv("openalex_window_2025.csv", index=False)

    report = [
        "ERJOR citation windows rebuilt from OpenAlex",
        f"retrieved {pd.Timestamp.today():%Y-%m-%d}",
        "",
        describe(w24, "2024 window (pub 2022-2023, cited during 2024)"),
        describe(w25, "2025 window (pub 2023-2024, cited during 2025)"),
        "CALIBRATION against Web of Science JCR 2024",
        "  WoS reported: 515 citable items, 74 zero (14.4%), "
        "103 one (19.9%), median 3, max 60",
        f"  OpenAlex    : {len(w24)} citable items, "
        f"{int((w24['Number of Citations'] == 0).sum())} zero "
        f"({(w24['Number of Citations'] == 0).mean() * 100:.1f}%), "
        f"median {w24['Number of Citations'].median():.0f}",
        "",
        "  Differences are expected. OpenAlex indexes a wider set of citing",
        "  sources than Web of Science, so it should find FEWER uncited",
        "  papers. Its document typing is also algorithmic, so the citable",
        "  denominator will not match exactly. Report the gap rather than",
        "  presenting either figure as the truth.",
    ]
    text = "\n".join(report)
    open("calibration.txt", "w").write(text)
    print("\n" + text)
    print("\nNext: python classify.py openalex_window_2025.csv labelled_2025.csv")


if __name__ == "__main__":
    main()
