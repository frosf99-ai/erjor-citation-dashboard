# ERJOR Editorial Intelligence Dashboard

A free Streamlit dashboard for ERJ Open Research using OpenAlex data.

## What it shows

### 1. Citation performance: 12-36 months
- Total papers published 12-36 months ago
- Estimated citations accrued in the first 12 months after publication
- Current total citations
- Median first-year citations
- Proportion with >=10 estimated first-year citations
- Citation trend for the cohort

Important: OpenAlex does not provide exact month-level historical citing dates in the free Works endpoint. The app estimates first-12-month citations from OpenAlex `counts_by_year` annual buckets. It also stores daily snapshots from the day the app starts running, which improves future trend analysis.

### 2. New papers: 0-12 months
- Total papers published in the last 12 months
- Article type breakdown: review, original research, editorial, correspondence, etc.
- Multi-theme breakdown
- Papers already being cited regularly
- Citations/month

### 3. Top 25 papers
- Title
- First author
- Theme/topic tags
- Citation count
- Estimated first-12-month citations
- Date/year of publication
- Article type
- DOI/link

### 4. Topic momentum
- Themes ranked by citation momentum
- Papers per theme
- Total citations
- 30/90-day gains when daily snapshots are available
- Citations per paper
- Top paper in each theme

## Theme tagging

Themes are non-exclusive. A paper can have more than one tag.

Disease/content themes include bronchiectasis, COPD, asthma, ILD, pulmonary vascular disease, respiratory infection, lung cancer, sleep medicine, pulmonary rehabilitation, critical care, respiratory physiology, imaging, digital health, airway disease, environmental/occupational lung disease, and rare lung disease.

Research type tags include clinical research, basic science, translational research, epidemiology, health services research, clinical trials, systematic review/meta-analysis, artificial intelligence, and implementation science.

The current classifier uses title, OpenAlex concepts/topics/keywords, and article metadata. It is deliberately transparent and editable in `app.py`.

## Deploy on Streamlit Community Cloud

1. Upload these files to your GitHub repository:
   - `app.py`
   - `fetch_openalex.py`
   - `requirements.txt`
2. In Streamlit Community Cloud, deploy with:
   - Main file path: `app.py`
   - Branch: usually `main`
3. Open the app and click **Fetch latest data now** in the sidebar.

## Notes on citation counts

OpenAlex and Google Scholar use different indexing methods, so counts will not always match. Google Scholar is usually broader and often higher. This app should be treated as an OpenAlex-based editorial intelligence tool, not a replacement for Google Scholar or Scopus.
