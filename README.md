# ERJ Open Research Impact Factor Tracker

A simplified Streamlit dashboard focused on two pages:

1. **Year to Date**
   - Total published in the selected year
   - Citable vs non-citable breakdown
   - Article type breakdown, e.g. original research, review, editorial, correspondence/letter
   - Topic/theme breakdown
   - Year-on-year comparison controls
   - Publication audit table with estimated citable status and reason

2. **Impact Factor**
   - OpenAlex-estimated Impact Factor
   - Citable-item denominator audit
   - Cumulative IF citation tracker by month or week
   - Current year compared with previous years using faded reference lines
   - What-if calculator

## Important note

This is an **OpenAlex-based estimate**, not the official Clarivate/Web of Science Journal Impact Factor. The denominator attempts to exclude editorials, letters, correspondence, research letters, corrections and similar non-citable items where the metadata or title indicates this.

## Deploy on Streamlit Community Cloud

Upload these files to your GitHub repository:

- `app.py`
- `fetch_openalex.py`
- `requirements.txt`
- `.github/workflows/update_data.yml`
- `README.md`

Then redeploy the Streamlit app with:

- Main file path: `app.py`
- Branch: `main`

## Data refresh

The app can fetch data from OpenAlex in the sidebar. The included GitHub Actions workflow can also refresh data daily.

OpenAlex recommends supplying an email address with API requests. The app uses `OPENALEX_MAILTO` if set, otherwise the sidebar value.
