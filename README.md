# Job Agent

`job-agent` is a Python pipeline that searches for entry-level AI, machine learning, data, and software roles, cleans the results, ranks them, and publishes the best opportunities to Google Sheets.

The current implementation is designed around one practical goal: help a Master's student in AI quickly find internships, junior roles, and thesis-friendly opportunities without manually checking multiple job boards every day.

## What The Project Does

The pipeline:

1. Fetches jobs from `python-jobspy` sources such as LinkedIn and Indeed.
2. Fetches additional remote jobs from Remotive.
3. Merges all sources into one dataset.
4. Removes low-quality rows and duplicates.
5. Scores every job locally with deterministic rules.
6. Optionally re-ranks the top jobs with Groq.
7. Saves CSV outputs in `data/`.
8. Optionally publishes both a technical sheet and a human-friendly view to Google Sheets.

This makes the repository part scraper, part ranking engine, and part lightweight publishing pipeline.

## How It Works

### 1. Fetch

The entrypoint is [main.py](/home/riccardo/Scrivania/job-agent/main.py).

It first loads `config.yaml`, then starts two collection phases:

- `scraper/jobspy_fetch.py`
  Queries JobSpy one site at a time to avoid one broken provider stopping the full run.
  It normalizes fields like title, company, location, salary, source, apply URL, and description into a shared schema.
- `scraper/remotive_fetch.py`
  Calls the Remotive public API, strips HTML from descriptions, and converts remote jobs into the same schema used by JobSpy.

The result of these two phases is written to:

- `data/jobspy_raw_jobs.csv`
- `data/remotive_raw_jobs.csv`
- `data/combined_raw_jobs.csv`

### 2. Clean And Deduplicate

The cleaning logic lives in [scraper/dedup.py](/home/riccardo/Scrivania/job-agent/scraper/dedup.py).

It:

- trims and normalizes text fields
- removes low-quality rows that do not have enough useful information
- keeps only recent jobs when `date_posted` can be parsed
- keeps jobs with unknown dates instead of discarding them
- removes duplicates by hashing `title + company + location`

This phase produces:

- `data/clean_jobs.csv`

### 3. Local Ranking

The main ranking engine is [agent/local_ranker.py](/home/riccardo/Scrivania/job-agent/agent/local_ranker.py).

This is the most important logic in the project because it gives you a fast and free first-pass ranking without needing an LLM.

The local ranker scores jobs using:

- internship and stage signals
- junior and entry-level signals
- target role keywords
- must-have and preferred skills
- location match
- freshness of the posting
- source-specific bonuses
- penalties for seniority or high experience requirements
- penalties for missing internship signals when internships are required

The local ranker adds columns such as:

- `local_rank`
- `local_fit_score`
- `match_bucket`
- `detected_skills`
- `internship_signals`
- `seniority_signals`
- `bad_signals`
- `experience_required_years`
- `local_score_reasons`

This phase writes:

- `data/ranked_jobs_local.csv`

### 4. AI Re-Ranking With Groq

The second ranking layer is [agent/groq_ranker.py](/home/riccardo/Scrivania/job-agent/agent/groq_ranker.py).

This module does not replace local ranking. It refines it.

Important details:

- it loads `GROQ_API_KEY` from the environment
- it batches jobs to reduce API calls
- it sends a compact version of each job, not the full raw row
- it combines the AI score with the local score
- it falls back to the local score if a Groq batch fails

The final score is computed as:

- `65% ai_fit_score`
- `35% local_fit_score`

This produces the final output:

- `data/ranked_jobs.csv`

### 5. Publish To Google Sheets

Publishing is handled by [output/sheets_writer.py](/home/riccardo/Scrivania/job-agent/output/sheets_writer.py) and [scripts/upload_ranked_csv_to_sheets.py](/home/riccardo/Scrivania/job-agent/scripts/upload_ranked_csv_to_sheets.py).

The publisher:

- authenticates with a Google service account
- opens the spreadsheet using `GOOGLE_SHEET_ID`
- writes a full technical worksheet
- writes a simplified dashboard worksheet
- applies formatting, column widths, and score coloring

The simplified view contains:

- `Rank`
- `Score`
- `Company`
- `Place`
- `Role`
- `Description`
- `Link`

## Repository Structure

```text
job-agent/
├── agent/
│   ├── groq_ranker.py
│   ├── local_ranker.py
│   ├── cv_parser.py
│   ├── scorer.py
│   ├── cv_analyser.py
│   └── bullet_gen.py
├── output/
│   └── sheets_writer.py
├── scraper/
│   ├── dedup.py
│   ├── jobspy_fetch.py
│   └── remotive_fetch.py
├── scripts/
│   └── upload_ranked_csv_to_sheets.py
├── .github/
│   └── workflows/
│       └── publish.yml
├── config.yaml
├── main.py
├── requirements.txt
├── job-agent-mvp.md
└── README.md
```

## Active Modules vs Legacy Files

The code currently used by the main pipeline is:

- `main.py`
- `scraper/jobspy_fetch.py`
- `scraper/remotive_fetch.py`
- `scraper/dedup.py`
- `agent/local_ranker.py`
- `agent/groq_ranker.py`
- `output/sheets_writer.py`
- `scripts/upload_ranked_csv_to_sheets.py`

There are also older or partial files in `agent/`:

- `agent/scorer.py`
- `agent/cv_parser.py`
- `agent/cv_analyser.py`
- `agent/bullet_gen.py`
- `job-agent-mvp.md`

These reflect earlier MVP ideas. Right now, the production path in `main.py` does not call `scorer.py`, `cv_analyser.py`, or `bullet_gen.py`.

## Configuration

The project is driven by [config.yaml](/home/riccardo/Scrivania/job-agent/config.yaml).

### `profile`

Describes the candidate:

- name
- current level
- target seniority

### `search`

Controls where and how jobs are fetched:

- `roles`
- `locations`
- `jobspy_sites`
- `country_indeed`
- `results_per_source`
- `hours_old`
- `distance`
- `linkedin_fetch_description`
- `verbose`
- `delay_seconds`

### `preferences`

Drives ranking:

- `must_have_skills`
- `preferred_stack`
- `nice_to_have`
- `exclusions`

### `remotive`

Controls the remote jobs source:

- `enabled`
- `search_terms`
- `limit_per_search`
- `delay_seconds`

### `sheets`

Controls worksheet names:

- `worksheet_name`
- `view_worksheet_name`

### `ai_ranking`

Controls Groq:

- `enabled`
- `model`
- `batch_size`
- `max_jobs_to_ai_rank`
- `max_description_chars`
- `max_output_tokens`
- `delay_seconds`

### `local_ranking`

Controls heuristic scoring rules:

- `enabled`
- `strict_internship_terms`
- `soft_entry_level_terms`
- `require_internship_signal`
- `no_internship_max_score`
- `target_role_terms`
- `bad_seniority_terms`

Important:
the current `config.yaml` uses `internship_terms`, while `agent/local_ranker.py` reads `strict_internship_terms`. That means the configured list is not fully controlling the runtime behavior yet. Right now the ranker falls back to its internal defaults unless you rename that config key or update the code.

## Data Flow

The pipeline data flow is:

```text
config.yaml
   |
   v
main.py
   |
   +--> JobSpy fetch -------------------+
   |                                    |
   +--> Remotive fetch -----------------+--> combined_raw_jobs.csv
                                        |
                                        v
                                clean_and_deduplicate_jobs
                                        |
                                        v
                                   clean_jobs.csv
                                        |
                                        v
                                  rank_jobs_locally
                                        |
                                        v
                               ranked_jobs_local.csv
                                        |
                                        v
                                rank_jobs_with_groq
                                        |
                                        v
                                  ranked_jobs.csv
                                        |
                                        v
                          upload_ranked_csv_to_sheets.py
                                        |
                                        v
                             Google Sheets: data + view
```

## Requirements

The Python dependencies are listed in [requirements.txt](/home/riccardo/Scrivania/job-agent/requirements.txt):

- `pandas`
- `pyyaml`
- `requests`
- `beautifulsoup4`
- `pdfplumber`
- `groq`
- `gspread`
- `google-auth`
- `python-dotenv`
- `tenacity`
- `python-jobspy`

## Environment Variables

For local execution and GitHub Actions, the important variables are:

- `GROQ_API_KEY`
  Required when `ai_ranking.enabled: true`.
- `GOOGLE_SHEET_ID`
  Required when publishing to Google Sheets.
- `GOOGLE_CREDENTIALS_JSON`
  Recommended for GitHub Actions.
- `GOOGLE_CREDENTIALS_FILE`
  Useful for local development instead of JSON-in-env.

An example file is provided in [.env.example](/home/riccardo/Scrivania/job-agent/.env.example).

## How To Run The Project Locally

### 1. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure the project

- update `config.yaml`
- add your secrets to `.env` or export them in your shell

### 3. Run the pipeline

```bash
python main.py
```

### 4. Publish the ranked CSV to Google Sheets

```bash
python scripts/upload_ranked_csv_to_sheets.py
```

## Output Files

The default output directory is `data/`.

Main generated files:

- `jobspy_raw_jobs.csv`
- `remotive_raw_jobs.csv`
- `combined_raw_jobs.csv`
- `clean_jobs.csv`
- `ranked_jobs_local.csv`
- `ranked_jobs.csv`

These files are useful both for debugging and for showing the project as a data pipeline in a portfolio context.

## GitHub Actions Publication

This repository now includes [.github/workflows/publish.yml](/home/riccardo/Scrivania/job-agent/.github/workflows/publish.yml).

The workflow:

- can be started manually with `workflow_dispatch`
- can run automatically on a daily schedule
- installs dependencies
- runs `python main.py`
- runs `python scripts/upload_ranked_csv_to_sheets.py`
- uploads the generated CSV files as GitHub Actions artifacts

### Required GitHub Secrets

Add these in `Settings -> Secrets and variables -> Actions`:

- `GROQ_API_KEY`
- `GOOGLE_SHEET_ID`
- `GOOGLE_CREDENTIALS_JSON`

If you disable AI ranking in `config.yaml`, `GROQ_API_KEY` is no longer needed for the pipeline itself.

## Publishing Notes

If your goal is to present this project publicly, the strongest story is:

- it solves a real personal workflow problem
- it combines scraping, cleaning, ranking, LLM re-ranking, and reporting
- it has a clear separation between collection, ranking, and publishing
- it can run unattended with GitHub Actions

That makes it a good portfolio project because it is both understandable and operational.

## Recommended Next Improvements

The current repository is already useful, but these are the next logical improvements:

1. Add tests for deduplication and local ranking rules.
2. Make all ranking thresholds fully configurable in `config.yaml`.
3. Remove or archive legacy MVP modules that are no longer part of the runtime path.
4. Add a small diagram or screenshot of the Google Sheets dashboard.
5. Add a pinned example dataset for demo purposes when real scraping is unavailable.

## GitHub Actions Guide

For a step-by-step deployment checklist, see [docs/GITHUB_ACTIONS_PUBLISHING.md](/home/riccardo/Scrivania/job-agent/docs/GITHUB_ACTIONS_PUBLISHING.md).
