# ERJOR YTD + Impact Factor + Decision Tracker

Streamlit dashboard for ERJ Open Research editorial monitoring.

## Pages

1. **Year to Date**
   - Total publications
   - Citable / non-citable split
   - Article type breakdown
   - Topic breakdown
   - Year comparison

2. **Impact Factor**
   - OpenAlex-estimated Impact Factor
   - Numerator / denominator
   - Cumulative IF-year citation tracker
   - Citable item audit
   - What-if calculator

3. **Decision Tracker**
   - Paste ScholarOne decision text directly into the app
   - Upload the existing ERJOR decisions `.ods`, `.csv` or `.xlsx`
   - Accepts/rejects per month
   - Study-type breakdown
   - Topic breakdown
   - Month-by-month tracker
   - Median time to decision
   - Downloadable decision records CSV

## Decision tracker notes

The Decision Tracker is designed to replicate the current Google Sheets workflow. It parses text blocks like:

```text
ERJOR-00118-2026 Submitted: 23-Jan-2026; Last Updated: 23-Jan-2026; In Review: 0sec ... Original Research Article Desk Reject
```

It extracts:

- manuscript ID
- submitted date
- decision date, using `Last Updated`
- study type
- decision
- simple topic tags
- estimated days to decision

On Streamlit Community Cloud, local files are not guaranteed to persist after redeploy/sleep. Use the **Download decision records CSV** button as the backup/export, then re-upload it when needed.

## Deploy

Upload/replace these files in your GitHub repository:

- `app.py`
- `fetch_openalex.py`
- `requirements.txt`
- `.github/workflows/update_data.yml`
- `README.md`

Then Streamlit should redeploy automatically.
