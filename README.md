# Job Agent

Automated Python pipeline for collecting, cleaning, deduplicating, ranking, and publishing job opportunities using configurable ranking rules and optional LLM-based re-ranking.

The project turns a noisy job-search process into a reproducible data pipeline: it gathers postings from multiple sources, standardizes them into a shared schema, removes duplicates, scores opportunities against a candidate profile, and publishes the best matches to a Google Sheets dashboard.

## Why this project matters

Job search is repetitive, noisy, and difficult to track manually:

* the same role often appears on multiple platforms
* many postings are too senior or not relevant enough
* job titles can look relevant while descriptions are not
* manually checking multiple sources every day does not scale

`job-agent` solves this as an applied data/AI engineering problem: collect data, normalize it, clean it, rank it, optionally improve ranking with an LLM, and publish a readable dashboard automatically.

## Key Features

* Collects postings from JobSpy-supported sources such as LinkedIn and Indeed
* Collects remote-first postings from Remotive
* Normalizes heterogeneous job sources into a shared schema
* Cleans weak rows and removes duplicate postings
* Filters jobs by freshness and configurable search constraints
* Scores opportunities with transparent local ranking rules
* Optionally re-ranks top results using Groq LLM inference
* Exports intermediate CSV files for debugging and analysis
* Publishes ranked results to a formatted Google Sheets dashboard
* Supports scheduled execution with GitHub Actions

## Tech Stack

| Area            | Technologies                                |
| --------------- | ------------------------------------------- |
| Language        | Python                                      |
| Data processing | pandas, CSV-based pipelines                 |
| Job collection  | JobSpy, Remotive API                        |
| Ranking         | rule-based scoring, configurable heuristics |
| LLM integration | Groq API                                    |
| Publishing      | Google Sheets API                           |
| Automation      | GitHub Actions                              |
| Configuration   | YAML, environment variables                 |

## Pipeline Overview

```text
config.yaml
   |
   v
main.py
   |
   +--> JobSpy fetch
   +--> Remotive fetch
   |
   v
combined_raw_jobs.csv
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
optional Groq re-ranking
   |
   v
ranked_jobs.csv
   |
   v
Google Sheets dashboard
```

## Main Components

| Area             | File                                     | Purpose                                       |
| ---------------- | ---------------------------------------- | --------------------------------------------- |
| Entrypoint       | `main.py`                                | Runs the full pipeline                        |
| JobSpy fetcher   | `scraper/jobspy_fetch.py`                | Fetches jobs from JobSpy-supported sources    |
| Remotive fetcher | `scraper/remotive_fetch.py`              | Fetches remote-first jobs from Remotive       |
| Cleaning         | `scraper/dedup.py`                       | Cleans rows and removes duplicate postings    |
| Local ranking    | `agent/local_ranker.py`                  | Scores jobs using deterministic ranking rules |
| AI ranking       | `agent/groq_ranker.py`                   | Optionally re-ranks top jobs with Groq        |
| Sheets writer    | `output/sheets_writer.py`                | Writes formatted Google Sheets output         |
| Upload script    | `scripts/upload_ranked_csv_to_sheets.py` | Publishes ranked results to Google Sheets     |

## Repository Structure

```text
job-agent/
├── agent/
│   ├── groq_ranker.py
│   ├── local_ranker.py
│   └── ...
├── scraper/
│   ├── dedup.py
│   ├── jobspy_fetch.py
│   └── remotive_fetch.py
├── output/
│   └── sheets_writer.py
├── scripts/
│   └── upload_ranked_csv_to_sheets.py
├── docs/
│   └── GITHUB_ACTIONS_PUBLISHING.md
├── .github/workflows/
│   └── publish.yml
├── config.yaml
├── main.py
├── requirements.txt
└── README.md
```

## Configuration

The pipeline is configured through `config.yaml`.

Main configuration sections:

* `profile`: candidate name, level, and target seniority
* `search`: roles, locations, sources, result limits, and freshness filters
* `preferences`: must-have skills, preferred stack, nice-to-have technologies, and exclusions
* `remotive`: Remotive search terms and limits
* `ai_ranking`: Groq model, batch size, limits, and enable/disable flag
* `local_ranking`: local scoring behavior and keyword rules
* `paths`: output directory and local file paths
* `sheets`: Google Sheets worksheet names

This makes the system reusable for different candidate profiles, target roles, locations, and ranking preferences.

## Output Files

By default, generated files are written to the configured output directory.

| File                    | Description                   |
| ----------------------- | ----------------------------- |
| `jobspy_raw_jobs.csv`   | Raw JobSpy results            |
| `remotive_raw_jobs.csv` | Raw Remotive results          |
| `combined_raw_jobs.csv` | Combined raw dataset          |
| `clean_jobs.csv`        | Cleaned and deduplicated jobs |
| `ranked_jobs_local.csv` | Locally ranked jobs           |
| `ranked_jobs.csv`       | Final ranked output           |

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/RicoDalB/job-agent.git
cd job-agent
```

### 2. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

On Windows:

```bash
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure the project

Edit `config.yaml` with your target roles, locations, sources, and ranking preferences.

Create a `.env` file from the example file:

```bash
cp .env.example .env
```

Then add the required environment variables depending on the features you want to use.

## Environment Variables

| Variable                  | Required                       | Purpose                           |
| ------------------------- | ------------------------------ | --------------------------------- |
| `GROQ_API_KEY`            | Only if AI ranking is enabled  | Enables Groq-based re-ranking     |
| `GOOGLE_SHEET_ID`         | Only for Sheets publishing     | Target spreadsheet ID             |
| `GOOGLE_CREDENTIALS_JSON` | Recommended for GitHub Actions | Google service account JSON       |
| `GOOGLE_CREDENTIALS_FILE` | Optional for local use         | Path to service account JSON file |

## Usage

Run the full pipeline:

```bash
python main.py
```

Publish the final ranked CSV to Google Sheets:

```bash
python scripts/upload_ranked_csv_to_sheets.py
```

Check that Python files compile:

```bash
python -m compileall main.py agent scraper output scripts
```

## Ranking Logic

The local ranker scores opportunities using explainable signals such as:

* role relevance
* internship, junior, and entry-level signals
* must-have skill matches
* preferred stack matches
* nice-to-have technology matches
* location fit
* posting freshness
* source quality
* seniority penalties
* experience requirement penalties

The optional Groq-based re-ranker is applied only to the highest-ranked local results. If AI ranking is disabled or an LLM request fails, the pipeline falls back to deterministic local ranking.

Final ranking combines local and AI-based scores:

```text
final_score = 0.65 * ai_fit_score + 0.35 * local_fit_score
```

## Google Sheets Dashboard

The Google Sheets publisher creates two worksheets:

1. **Data sheet**: full technical output with scores, reasons, metadata, links, and descriptions.
2. **View sheet**: simplified dashboard with rank, score, company, location, role, description, and application link.

The writer also applies spreadsheet formatting, including frozen headers, column widths, and score-based visual highlighting.

To enable publishing:

1. Create a Google Cloud project
2. Enable Google Sheets API and Google Drive API
3. Create a service account
4. Download the JSON key
5. Share the spreadsheet with the service account email
6. Set `GOOGLE_SHEET_ID`
7. Set `GOOGLE_CREDENTIALS_JSON` or `GOOGLE_CREDENTIALS_FILE`

For the full setup guide, see:

```text
docs/GITHUB_ACTIONS_PUBLISHING.md
```

## GitHub Actions Automation

The repository includes a GitHub Actions workflow in:

```text
.github/workflows/publish.yml
```

The workflow can:

* run manually with `workflow_dispatch`
* run automatically using cron
* install dependencies
* execute the full pipeline
* publish ranked results to Google Sheets
* store CSV outputs as workflow artifacts

Current schedule:

```cron
0 6 * * *
```

GitHub Actions cron schedules run in UTC.

Required repository secrets:

* `GOOGLE_SHEET_ID`
* `GOOGLE_CREDENTIALS_JSON`
* `GROQ_API_KEY`, if AI ranking is enabled

## Example Use Case

A candidate can define:

* target roles, such as AI intern, ML engineer intern, data scientist intern, or software engineer intern
* preferred locations, such as Europe, remote, or selected countries
* must-have skills, such as Python, machine learning, NLP, LLMs, or backend development
* exclusions, such as senior-only roles or unrelated job categories

The pipeline then produces a ranked list of opportunities that can be reviewed directly from Google Sheets.

## Portfolio Value

This project demonstrates practical skills in:

* data collection from multiple sources
* data cleaning and normalization
* deduplication logic
* configurable ranking systems
* LLM-assisted decision support
* Google Sheets reporting
* scheduled automation with GitHub Actions
* Python project organization
* environment-based configuration

It is designed as a practical applied AI engineering project rather than a simple script.

## Known Limitations

* Job sources may change their structure, availability, or access behavior over time
* Ranking quality depends on the configured candidate profile and keyword rules
* GitHub Actions execution depends on valid repository secrets and external API availability
* Automated tests are planned but not yet included


