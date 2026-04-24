# Job Agent

`job-agent` is an automated Python pipeline that collects fresh job postings, cleans and deduplicates them, ranks them against a candidate profile, and publishes the results to Google Sheets.

The repository is built around a practical use case: helping a Master's student in Artificial Intelligence find internships, junior roles, thesis opportunities, and entry-level AI/data/software jobs without manually checking multiple job boards every day.

## Why This Project Exists

Job searching is repetitive and noisy:

- the same job appears on multiple platforms
- many postings are too senior
- many titles look relevant but are not
- reviewing every listing manually takes too much time

This project reduces that work by turning job search into a small data pipeline:

1. collect jobs from multiple sources
2. normalize them into one schema
3. remove duplicates and weak rows
4. score them using explicit ranking rules
5. optionally re-rank the best ones with Groq
6. export everything as CSV
7. publish a clean dashboard to Google Sheets

## What The Project Does

At a high level, the repository has three responsibilities:

### 1. Job collection

It fetches jobs from:

- `python-jobspy` sources like LinkedIn and Indeed
- Remotive for remote-first opportunities

### 2. Ranking

It ranks jobs in two stages:

- a local deterministic scoring engine
- an optional AI re-ranking pass with Groq

### 3. Publishing

It saves the results locally and can publish them to Google Sheets in two formats:

- a technical data sheet with full columns
- a simplified human-friendly dashboard view

## Main Features

- multi-source job collection
- shared normalized schema across sources
- duplicate removal across platforms
- recency filtering
- local ranking with explainable scoring reasons
- AI ranking with Groq for the top jobs
- CSV outputs for debugging and analysis
- Google Sheets publishing
- scheduled execution with GitHub Actions

## How The Pipeline Works

The runtime entrypoint is [main.py](/home/riccardo/Scrivania/job-agent/main.py).

The current pipeline is organized into five phases.

### Phase 1. Fetch jobs from JobSpy

Implemented in [scraper/jobspy_fetch.py](/home/riccardo/Scrivania/job-agent/scraper/jobspy_fetch.py).

This module:

- reads target roles, locations, and sources from `config.yaml`
- queries one JobSpy source at a time
- avoids one provider failure breaking the full run
- normalizes provider output into a shared dataframe schema

The normalized columns include:

- `title`
- `company`
- `location`
- `source`
- `date_posted`
- `apply_url`
- `description`
- `search_role`
- `search_location`

### Phase 2. Fetch jobs from Remotive

Implemented in [scraper/remotive_fetch.py](/home/riccardo/Scrivania/job-agent/scraper/remotive_fetch.py).

This module:

- calls the Remotive API
- searches multiple configured terms
- strips HTML from descriptions
- converts results to the same schema used by JobSpy

### Phase 3. Clean and deduplicate

Implemented in [scraper/dedup.py](/home/riccardo/Scrivania/job-agent/scraper/dedup.py).

This step:

- strips and normalizes text columns
- removes low-quality rows
- filters by job age using `hours_old`
- keeps rows with unknown dates instead of aggressively discarding them
- generates a stable deduplication key from `title + company + location`
- drops duplicate jobs that appear across multiple platforms

### Phase 4. Local ranking

Implemented in [agent/local_ranker.py](/home/riccardo/Scrivania/job-agent/agent/local_ranker.py).

This is the main scoring engine of the repository.

It scores each job using transparent heuristics such as:

- internship and stage signals
- junior and entry-level signals
- role keyword relevance
- must-have skills
- preferred stack matches
- nice-to-have technologies
- location fit
- freshness bonuses
- source bonuses
- seniority penalties
- experience requirement penalties
- penalties for missing internship signals

The local ranker enriches each job with fields such as:

- `local_rank`
- `local_fit_score`
- `match_bucket`
- `detected_skills`
- `internship_signals`
- `seniority_signals`
- `bad_signals`
- `experience_required_years`
- `local_score_reasons`

### Phase 5. AI re-ranking with Groq

Implemented in [agent/groq_ranker.py](/home/riccardo/Scrivania/job-agent/agent/groq_ranker.py).

This stage is optional and controlled by `config.yaml`.

It:

- loads `GROQ_API_KEY`
- converts jobs into a compact format
- sends batches to Groq instead of one long request per full row
- returns `ai_fit_score`, `ai_bucket`, and `ai_reason`
- falls back to the local score if an AI batch fails

The final score is computed in code as:

```text
final_score = 0.65 * ai_fit_score + 0.35 * local_fit_score
```

The final output is sorted and assigned `final_rank`.

## Data Flow

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

## Repository Structure

```text
job-agent/
├── agent/
│   ├── __init__.py
│   ├── bullet_gen.py
│   ├── cv_analyser.py
│   ├── cv_parser.py
│   ├── groq_ranker.py
│   ├── local_ranker.py
│   └── scorer.py
├── docs/
│   └── GITHUB_ACTIONS_PUBLISHING.md
├── output/
│   ├── __init__.py
│   └── sheets_writer.py
├── scraper/
│   ├── __init__.py
│   ├── dedup.py
│   ├── jobspy_fetch.py
│   └── remotive_fetch.py
├── scripts/
│   └── upload_ranked_csv_to_sheets.py
├── .github/
│   └── workflows/
│       └── publish.yml
├── .env.example
├── config.yaml
├── job-agent-mvp.md
├── main.py
├── requirements.txt
└── README.md
```

## Active Runtime Path

The current runtime path used by the project is:

- [main.py](/home/riccardo/Scrivania/job-agent/main.py)
- [scraper/jobspy_fetch.py](/home/riccardo/Scrivania/job-agent/scraper/jobspy_fetch.py)
- [scraper/remotive_fetch.py](/home/riccardo/Scrivania/job-agent/scraper/remotive_fetch.py)
- [scraper/dedup.py](/home/riccardo/Scrivania/job-agent/scraper/dedup.py)
- [agent/local_ranker.py](/home/riccardo/Scrivania/job-agent/agent/local_ranker.py)
- [agent/groq_ranker.py](/home/riccardo/Scrivania/job-agent/agent/groq_ranker.py)
- [output/sheets_writer.py](/home/riccardo/Scrivania/job-agent/output/sheets_writer.py)
- [scripts/upload_ranked_csv_to_sheets.py](/home/riccardo/Scrivania/job-agent/scripts/upload_ranked_csv_to_sheets.py)

## Legacy Or Partial Modules

There are also older or not-currently-used files in `agent/`:

- [agent/scorer.py](/home/riccardo/Scrivania/job-agent/agent/scorer.py)
- [agent/cv_parser.py](/home/riccardo/Scrivania/job-agent/agent/cv_parser.py)
- [agent/cv_analyser.py](/home/riccardo/Scrivania/job-agent/agent/cv_analyser.py)
- [agent/bullet_gen.py](/home/riccardo/Scrivania/job-agent/agent/bullet_gen.py)
- [job-agent-mvp.md](/home/riccardo/Scrivania/job-agent/job-agent-mvp.md)

These reflect an earlier MVP direction that included CV analysis and tailored bullet generation. The current `main.py` pipeline does not call those modules.

## Configuration

The repository is driven by [config.yaml](/home/riccardo/Scrivania/job-agent/config.yaml).

The main sections are:

### `profile`

Describes the candidate:

- name
- current level
- target seniority

### `search`

Controls fetching:

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

Controls ranking preference signals:

- `must_have_skills`
- `preferred_stack`
- `nice_to_have`
- `exclusions`

### `remotive`

Controls Remotive collection:

- `enabled`
- `search_terms`
- `limit_per_search`
- `delay_seconds`

### `scoring`

Contains thresholds used for bucket interpretation in the broader project setup.

### `paths`

Controls local file locations such as:

- `cv_path`
- `output_dir`

### `sheets`

Controls Google Sheets worksheet names:

- `worksheet_name`
- `view_worksheet_name`

### `ai_ranking`

Controls Groq AI ranking:

- `enabled`
- `model`
- `batch_size`
- `max_jobs_to_ai_rank`
- `max_description_chars`
- `max_output_tokens`
- `delay_seconds`

### `local_ranking`

Controls heuristic local ranking behavior:

- `enabled`
- `target_role_terms`
- `bad_seniority_terms`

The code in [agent/local_ranker.py](/home/riccardo/Scrivania/job-agent/agent/local_ranker.py) also supports:

- `strict_internship_terms`
- `soft_entry_level_terms`
- `require_internship_signal`
- `no_internship_max_score`

Important note:
the current `config.yaml` uses `internship_terms`, while `agent/local_ranker.py` reads `strict_internship_terms`. That means the configured internship list is not fully wired to the current runtime behavior yet unless the config key is renamed or the code is updated.

## Output Files

By default, generated files are written to `data/`.

The main outputs are:

- `jobspy_raw_jobs.csv`
- `remotive_raw_jobs.csv`
- `combined_raw_jobs.csv`
- `clean_jobs.csv`
- `ranked_jobs_local.csv`
- `ranked_jobs.csv`

These are useful for:

- debugging
- validating ranking rules
- demonstrating the data pipeline in a portfolio
- keeping a local archive of collected results

## Google Sheets Publishing

Publishing is handled by:

- [output/sheets_writer.py](/home/riccardo/Scrivania/job-agent/output/sheets_writer.py)
- [scripts/upload_ranked_csv_to_sheets.py](/home/riccardo/Scrivania/job-agent/scripts/upload_ranked_csv_to_sheets.py)

The uploader reads `data/ranked_jobs.csv` and writes two worksheets:

### Data worksheet

A technical sheet with full scoring and metadata columns such as:

- final scores
- local scores
- AI scores
- ranking reasons
- detected skills
- source data
- apply URL
- description

### View worksheet

A simplified dashboard with:

- `Rank`
- `Score`
- `Company`
- `Place`
- `Role`
- `Description`
- `Link`

The writer also applies:

- frozen header row
- formatting
- column widths
- score-based coloring

## Environment Variables

The project uses environment variables for secrets and external integrations.

The main ones are:

- `GROQ_API_KEY`
- `GOOGLE_SHEET_ID`
- `GOOGLE_CREDENTIALS_JSON`
- `GOOGLE_CREDENTIALS_FILE`

An example template is available in [.env.example](/home/riccardo/Scrivania/job-agent/.env.example).

### What each variable is for

- `GROQ_API_KEY`
  Required only if AI ranking is enabled.
- `GOOGLE_SHEET_ID`
  Required for Google Sheets publishing.
- `GOOGLE_CREDENTIALS_JSON`
  Recommended in GitHub Actions.
- `GOOGLE_CREDENTIALS_FILE`
  Useful for local development when using a service account JSON file on disk.

## Requirements

The project dependencies are listed in [requirements.txt](/home/riccardo/Scrivania/job-agent/requirements.txt).

Main libraries:

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

## Local Setup

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd job-agent
```

### 2. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure the project

- update `config.yaml` for your target roles, locations, and preferences
- create a local `.env` file or export the needed environment variables
- set up Google Sheets credentials if you want publishing

### 5. Run the pipeline

```bash
python main.py
```

### 6. Upload the final CSV to Google Sheets

```bash
python scripts/upload_ranked_csv_to_sheets.py
```

## GitHub Actions Automation

The repository includes [publish.yml](/home/riccardo/Scrivania/job-agent/.github/workflows/publish.yml).

This workflow:

- checks out the repo
- installs Python and dependencies
- runs the pipeline
- uploads the ranked results to Google Sheets
- stores generated CSV files as artifacts

### Workflow triggers

- manual trigger through `workflow_dispatch`
- scheduled daily trigger through cron

The current workflow schedule is:

```text
0 6 * * *
```

GitHub Actions cron uses UTC.

### Required GitHub Secrets

To run the workflow successfully, add these repository secrets:

- `GROQ_API_KEY`
- `GOOGLE_SHEET_ID`
- `GOOGLE_CREDENTIALS_JSON`

If AI ranking is disabled in `config.yaml`, the pipeline itself does not need `GROQ_API_KEY`.

For a step-by-step workflow guide, see [docs/GITHUB_ACTIONS_PUBLISHING.md](/home/riccardo/Scrivania/job-agent/docs/GITHUB_ACTIONS_PUBLISHING.md).

## Google Sheets Setup Summary

To enable publication:

1. create a Google Cloud project
2. enable Google Sheets API and Google Drive API
3. create a service account
4. download the JSON key
5. share your spreadsheet with the service account email
6. store the spreadsheet ID in `GOOGLE_SHEET_ID`
7. store the JSON key in `GOOGLE_CREDENTIALS_JSON` or point to it via `GOOGLE_CREDENTIALS_FILE`

## What Makes This Project Useful In A Portfolio

This repository is a good portfolio project because it combines:

- web data collection
- schema normalization
- data cleaning
- heuristic ranking
- LLM integration
- reporting and dashboard publication
- automation through CI/CD

It is also easy to explain to interviewers because the input, pipeline, and output are concrete and visible.

## Current Limitations

The current implementation works well as a practical personal pipeline, but there are some known limitations:

- external scraping sources may fail or change behavior
- ranking logic is tuned to one candidate profile
- some older modules remain in the repo even though they are not used
- there are currently no automated tests in the repository
- the internship config key naming is not fully aligned with the local ranker
- GitHub Actions success depends on valid external secrets and API availability

## Recommended Next Improvements

The most valuable next steps would be:

1. add automated tests for deduplication and ranking
2. align `config.yaml` and `local_ranker.py` key names
3. remove or archive unused MVP modules
4. add screenshots of the Google Sheets dashboard
5. add sample data for demo runs
6. make more ranking parameters configurable without touching code

## Quick Command Reference

Run the full pipeline:

```bash
python main.py
```

Publish the ranked CSV to Sheets:

```bash
python scripts/upload_ranked_csv_to_sheets.py
```

Check that the Python files compile:

```bash
python -m compileall main.py agent scraper output scripts
```

## Summary

`job-agent` is a small but complete job discovery system:

- it gathers jobs from multiple sources
- it filters and ranks them
- it explains why jobs scored the way they did
- it exports structured data
- it can publish a readable dashboard automatically

That makes it both useful in daily life and strong as a GitHub project because it demonstrates practical engineering, automation, and product thinking in one repository.
