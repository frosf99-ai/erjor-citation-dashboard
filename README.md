# ERJOR Editorial Intelligence Dashboard

A branded Streamlit dashboard for ERJ Open Research citation intelligence using OpenAlex.

## What it shows

1. **Citation Performance (12-36 month cohort)**
   - Papers published 12-36 months ago
   - Lifetime citations
   - Estimated citations in the last 365 days
   - Mean/median recent citations
   - Top 25 papers by recent citations
   - Theme and article type performance

2. **New Papers (0-12 months)**
   - Article type breakdown
   - Multi-theme breakdown
   - Clinical research / basic science / translational tags
   - Papers already gaining citation traction

3. **Topic Momentum**
   - Themes ranked by recent citation momentum
   - Bubble chart and top paper per theme

4. **Editorial Intelligence**
   - Rising stars
   - High-potential new papers
   - Hidden gems
   - Commissioning opportunities

5. **Estimated Impact Factor**
   - OpenAlex-based JIF-style estimate
   - Previous two-year denominator
   - Excludes editorials, letters, correspondence and research letters where identifiable
   - Citable items audit table
   - Month-by-month or week-by-week cumulative IF citation tracker comparing the selected year with the previous year
   - What-if calculator

6. **Editorial Board Report**
   - One-page summary with CSV export

## Important citation note

OpenAlex `cited_by_count` is a lifetime citation total. The dashboard estimates **citations in the last 365 days** from OpenAlex `counts_by_year` by prorating annual citation buckets. This is suitable for editorial monitoring, but exact day-level recent citation counts would require fetching every citing work and checking its publication date.

Google Scholar counts are often higher than OpenAlex because Google Scholar indexes a broader range of sources and does not provide a public API.

## Deploy on Streamlit Community Cloud

1. Upload these files to your GitHub repository.
2. On Streamlit Community Cloud, deploy the app.
3. Set the main file path to:

```text
app.py
```

4. Open the app and click **Fetch latest data now** in the sidebar.

## Optional daily refresh with GitHub Actions

This package includes:

```text
.github/workflows/update_data.yml
```

The workflow runs daily and commits the refreshed SQLite database back to the repository. It fetches a 0-60 month publication window so the Impact Factor page can estimate current and recent two-year denominator windows.

Recommended: add a GitHub repository secret:

```text
OPENALEX_MAILTO=your.email@example.com
```

OpenAlex recommends including a mailto email address for polite API usage.

## Files

- `app.py` - Streamlit dashboard
- `fetch_openalex.py` - OpenAlex data fetcher and SQLite updater
- `requirements.txt` - Python dependencies
- `.github/workflows/update_data.yml` - optional daily refresh workflow


## Estimated Impact Factor method

The estimated Impact Factor is not the official Clarivate Journal Impact Factor. It uses OpenAlex citation data and approximates the standard JIF structure:

```text
Citations in selected year to ERJOR items published in the previous two years
/
Citable ERJOR items published in the previous two years
```

The denominator includes articles/research papers and reviews where identifiable. It excludes editorials, letters, research letters, correspondence, corrections, errata, retractions and similar non-citable items where identifiable from OpenAlex/Crossref metadata or title rules. The app includes a citable-items audit table so these decisions are transparent.


### Cumulative IF citation tracker

The Impact Factor page includes a tracker showing cumulative citations across Jan-Dec for the selected IF year, with the previous year as a comparison. You can switch between monthly and weekly views. Because the lightweight OpenAlex work record provides `counts_by_year` rather than exact citation dates, the tracker prorates annual citation buckets across the selected periods. It is therefore best treated as a live directional tracker rather than an official Web of Science monthly citation feed.
