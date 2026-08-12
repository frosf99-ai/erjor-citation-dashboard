# ERJOR Citation Analysis

A browser-based tool for the ERJ Open Research editorial meeting: it rebuilds
journal-impact-factor citation windows, identifies zero-cited papers, and codes
every paper by disease theme and study methodology.

Nothing needs installing to use it — once deployed, it runs in a web browser.

---

## What it does

A journal impact factor counts citations received **during a single year** by
items published in the **two preceding years**. OpenAlex records citations per
year for every paper, so that window can be rebuilt exactly rather than
approximated:

| Window | Papers published | Citations counted during |
|---|---|---|
| JCR 2024 | 2022 + 2023 | 2024 |
| JCR 2025 | 2023 + 2024 | 2025 |

Because 2023 papers appear in both windows, the same papers can be tracked
across them — separating papers that were merely slow to be cited from those
that remain persistently uncited.

Every paper is then coded on two axes using a fixed rule set. The same title
always produces the same label, and each assignment records the rules that
produced it, so any classification can be audited.

## What you get

- Headline figures: items, zero-citation count, 0–1 count, median, distribution
- Zero-citation rates by disease theme and by methodology, with denominators
- Theme × methodology heatmap showing where uncitedness concentrates
- Year-on-year movement, and the catch-up analysis on overlapping papers
- An editable table of zero-cited papers for manual correction
- Calibration against the known Web of Science result for 2024
- CSV and Excel downloads

---

## Deploying it (one-time, about 30 minutes)

### 1. Create a GitHub account

Go to [github.com](https://github.com) and sign up if you don't have one.
The free tier is all that's needed.

### 2. Create a repository

Click **+** (top right) → **New repository**. Name it `erjor-citation-analysis`.
Choose **Public** — Streamlit's free tier requires it, and there's nothing
sensitive here. Don't tick any of the initialisation options. Click
**Create repository**.

### 3. Upload the files

On the new empty repository page, click **uploading an existing file**.
Drag in all five:

```
app.py               the interface
classify.py          the coding rules
fetch_openalex.py    the OpenAlex data pull
requirements.txt     tells Streamlit what to install
README.md            this file
```

Click **Commit changes**.

### 4. Deploy

Go to [share.streamlit.io](https://share.streamlit.io) and sign in with
GitHub. Click **Create app** → **Deploy a public app from GitHub**. Select
your repository, leave the branch as `main`, set the main file path to
`app.py`, and click **Deploy**.

First build takes 2–3 minutes. You'll get a permanent URL like
`erjor-citation-analysis.streamlit.app` that you can share with the board.

### 5. Use it

Enter your email in the sidebar (OpenAlex asks for it to grant faster API
access; it isn't stored), set the windows, and click **Fetch and analyse**.

---

## Updating the coding rules

All classification logic is in `classify.py`, in two lists: `THEMES` and
`METHODS`. Each entry is a label and the regular expressions that trigger it.
Rules are applied in order, most specific first.

To change a rule, edit `classify.py` on GitHub (click the file, then the pencil
icon) and commit. Streamlit redeploys automatically within a minute or so.

The app and the command-line scripts share this file, so a change applies to
both.

## Command-line use

The same analysis without the interface:

```bash
pip install -r requirements.txt
python fetch_openalex.py --mailto you@example.com
python classify.py openalex_window_2025.csv labelled_2025.csv
```

## Interpreting the output

**Compare OpenAlex to OpenAlex.** OpenAlex indexes a wider set of citing
sources than Web of Science, so it finds fewer uncited papers. Its figures are
not directly comparable to a JCR number from a previous year. The app builds
both windows from the same database precisely so the comparison is valid.

**Check the calibration tab.** Setting one window to 2024 compares the app's
output against the known Web of Science result (515 citable items, 74 zeros).
If the item count differs by more than roughly 20%, something is wrong and the
figures shouldn't be presented.

**Read rates against denominators.** A theme with four papers and one uncited
scores 25%, which means very little. The tables show `Papers` alongside every
rate, and the minimum-size sliders exist for this reason.

**Titles are all the coder sees.** A mechanistic study with a clinical-sounding
title will be misfiled. Papers where few rules fired are marked as low
confidence, and that is where errors concentrate.

## Limitations

- Citation counts are a proxy for attention, not quality or clinical value
- Recent publication years are still accruing citations
- OpenAlex document typing is algorithmic and imperfect
- Disease themes overlap in reality; the `Theme_all_matches` column records
  every theme a paper matched, not just the assigned one
