"""Fetch ERJ Open Research citation snapshots from OpenAlex.

Run daily, e.g.:
    python fetch_openalex.py --mailto your.email@example.com

The script stores one snapshot per work per day in SQLite. OpenAlex gives the
current cited_by_count; this local history lets the dashboard calculate trends.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sqlite3
import time
from typing import Any

import requests

DB_PATH = "erjor_citations.sqlite"
OPENALEX_BASE = "https://api.openalex.org/works"
ERJOR_ISSN = "2312-0541"

SELECT_FIELDS = ",".join([
    "id",
    "doi",
    "display_name",
    "publication_date",
    "publication_year",
    "cited_by_count",
    "authorships",
    "primary_location",
    "locations_count",
    "type",
    "ids",
])


def connect(db_path: str) -> sqlite3.Connection:
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS works (
            openalex_id TEXT PRIMARY KEY,
            doi TEXT,
            title TEXT,
            publication_date TEXT,
            publication_year INTEGER,
            work_type TEXT,
            source_display_name TEXT,
            landing_page_url TEXT,
            authors TEXT,
            institutions TEXT,
            updated_at TEXT NOT NULL
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS citation_snapshots (
            snapshot_date TEXT NOT NULL,
            openalex_id TEXT NOT NULL,
            cited_by_count INTEGER NOT NULL,
            PRIMARY KEY (snapshot_date, openalex_id),
            FOREIGN KEY(openalex_id) REFERENCES works(openalex_id)
        )
        """
    )
    return con


def safe_get(obj: dict[str, Any] | None, path: list[str], default: Any = None) -> Any:
    cur: Any = obj or {}
    for key in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
        if cur is None:
            return default
    return cur


def extract_authors(authorships: list[dict[str, Any]]) -> str:
    names = []
    for a in authorships or []:
        name = safe_get(a, ["author", "display_name"])
        if name:
            names.append(name)
    return "; ".join(names)


def extract_institutions(authorships: list[dict[str, Any]]) -> str:
    institutions: list[str] = []
    seen: set[str] = set()
    for a in authorships or []:
        for inst in a.get("institutions", []) or []:
            name = inst.get("display_name")
            if name and name not in seen:
                seen.add(name)
                institutions.append(name)
    return "; ".join(institutions)


def fetch_page(cursor: str, mailto: str | None) -> dict[str, Any]:
    params = {
        "filter": f"primary_location.source.issn:{ERJOR_ISSN}",
        "select": SELECT_FIELDS,
        "per-page": 200,
        "cursor": cursor,
        "sort": "publication_date:desc",
    }
    if mailto:
        params["mailto"] = mailto
    response = requests.get(OPENALEX_BASE, params=params, timeout=60)
    response.raise_for_status()
    return response.json()


def upsert_work(con: sqlite3.Connection, work: dict[str, Any], snapshot_date: str) -> None:
    location = work.get("primary_location") or {}
    source = location.get("source") or {}
    con.execute(
        """
        INSERT INTO works (
            openalex_id, doi, title, publication_date, publication_year,
            work_type, source_display_name, landing_page_url, authors,
            institutions, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(openalex_id) DO UPDATE SET
            doi=excluded.doi,
            title=excluded.title,
            publication_date=excluded.publication_date,
            publication_year=excluded.publication_year,
            work_type=excluded.work_type,
            source_display_name=excluded.source_display_name,
            landing_page_url=excluded.landing_page_url,
            authors=excluded.authors,
            institutions=excluded.institutions,
            updated_at=excluded.updated_at
        """,
        (
            work.get("id"),
            work.get("doi"),
            work.get("display_name"),
            work.get("publication_date"),
            work.get("publication_year"),
            work.get("type"),
            source.get("display_name"),
            location.get("landing_page_url"),
            extract_authors(work.get("authorships", [])),
            extract_institutions(work.get("authorships", [])),
            dt.datetime.now(dt.UTC).isoformat(),
        ),
    )
    con.execute(
        """
        INSERT INTO citation_snapshots (snapshot_date, openalex_id, cited_by_count)
        VALUES (?, ?, ?)
        ON CONFLICT(snapshot_date, openalex_id) DO UPDATE SET
            cited_by_count=excluded.cited_by_count
        """,
        (snapshot_date, work.get("id"), int(work.get("cited_by_count") or 0)),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=DB_PATH)
    parser.add_argument("--mailto", default=None, help="Recommended by OpenAlex for polite API usage")
    parser.add_argument("--snapshot-date", default=dt.date.today().isoformat())
    args = parser.parse_args()

    con = connect(args.db)
    cursor = "*"
    total = 0
    while True:
        data = fetch_page(cursor, args.mailto)
        results = data.get("results", [])
        if not results:
            break
        with con:
            for work in results:
                upsert_work(con, work, args.snapshot_date)
                total += 1
        next_cursor = data.get("meta", {}).get("next_cursor")
        if not next_cursor or next_cursor == cursor:
            break
        cursor = next_cursor
        time.sleep(0.2)
    print(f"Saved {total} ERJOR works for snapshot {args.snapshot_date} into {args.db}")


if __name__ == "__main__":
    main()
