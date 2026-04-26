# Job Agent

Automated Python pipeline that collects fresh job postings, cleans and deduplicates them, ranks them against a candidate profile, and publishes the best results to Google Sheets.

This project was built for a Master's student in Artificial Intelligence looking for internships, thesis opportunities, junior roles, and entry-level AI/data/software jobs without manually checking multiple job boards every day.

## Why It Exists

Job searching is repetitive and noisy:

- the same role appears on multiple platforms
- many postings are too senior
- titles can look relevant while the description is not
- manually reviewing listings every day takes time

`job-agent` turns job search into a small data pipeline: collect jobs, normalize them, remove duplicates, rank them, and publish a clean dashboard.

## Features

- Collects jobs from JobSpy-supported sources such as LinkedIn and Indeed
- Collects remote-first jobs from Remotive
- Normalizes all sources into a shared schema
- Removes weak rows and duplicate postings
- Filters by posting age
- Scores jobs with transparent local ranking rules
- Optionally re-ranks top jobs with Groq
- Exports CSV files for debugging and analysis
- Publishes results to Google Sheets
- Supports scheduled runs with GitHub Actions

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

| Area | File | Purpose |
|---|---|---|
| Entrypoint | `main.py` | Runs the full pipeline |
| JobSpy fetcher | `scraper/jobspy_fetch.py` | Fetches jobs from JobSpy sources |
| Remotive fetcher | `scraper/remotive_fetch.py` | Fetches remote-first jobs from Remotive |
| Cleaning | `scraper/dedup.py` | Cleans rows and removes duplicates |
| Local ranking | `agent/local_ranker.py` | Scores jobs with deterministic rules |
| AI ranking | `agent/groq_ranker.py` | Optionally re-ranks top jobs with Groq |
| Sheets writer | `output/sheets_writer.py` | Writes formatted Google Sheets output |
| Upload script | `scripts/upload_ranked_csv_to_sheets.py` | Publishes `ranked_jobs.csv` to Sheets |

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

The project is configured through `config.yaml`.

Main sections:

- `profile`: candidate name, level, and target seniority
- `search`: roles, locations, sources, result limits, and freshness filters
- `preferences`: must-have skills, preferred stack, nice-to-have technologies, and exclusions
- `remotive`: Remotive search terms and limits
- `ai_ranking`: Groq model, batch size, limits, and enable/disable flag
- `local_ranking`: local scoring behavior and keyword rules
- `paths`: output directory and local file paths
- `sheets`: Google Sheets worksheet names

> Note: the current configuration uses `internship_terms`, while `agent/local_ranker.py` expects `strict_internship_terms`. Rename the config key or update the ranker so the internship terms are fully wired into the runtime behavior.

## Output Files

By default, generated files are written to `data/`.

| File | Description |
|---|---|
| `jobspy_raw_jobs.csv` | Raw JobSpy results |
| `remotive_raw_jobs.csv` | Raw Remotive results |
| `combined_raw_jobs.csv` | Combined raw dataset |
| `clean_jobs.csv` | Cleaned and deduplicated jobs |
| `ranked_jobs_local.csv` | Locally ranked jobs |
| `ranked_jobs.csv` | Final ranked output |

## Setup

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

Create a `.env` file or export the required environment variables.

```bash
cp .env.example .env
```

## Environment Variables

| Variable | Required | Purpose |
|---|---:|---|
| `GROQ_API_KEY` | Only if AI ranking is enabled | Enables Groq re-ranking |
| `GOOGLE_SHEET_ID` | Only for Sheets publishing | Target spreadsheet ID |
| `GOOGLE_CREDENTIALS_JSON` | Recommended for GitHub Actions | Google service account JSON |
| `GOOGLE_CREDENTIALS_FILE` | Optional for local use | Path to service account JSON file |

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

## Google Sheets Publishing

The Sheets publisher creates two worksheets:

1. **Data sheet**: technical output with full ranking fields, scores, reasons, source metadata, links, and descriptions.
2. **View sheet**: simplified dashboard with rank, score, company, location, role, description, and application link.

The writer also applies formatting such as frozen headers, column widths, and score-based coloring.

To enable publishing:

1. Create a Google Cloud project
2. Enable Google Sheets API and Google Drive API
3. Create a service account
4. Download the JSON key
5. Share your spreadsheet with the service account email
6. Set `GOOGLE_SHEET_ID`
7. Set `GOOGLE_CREDENTIALS_JSON` or `GOOGLE_CREDENTIALS_FILE`

See `docs/GITHUB_ACTIONS_PUBLISHING.md` for the full setup guide.

## GitHub Actions

The repository includes `.github/workflows/publish.yml`.

The workflow can:

- run manually with `workflow_dispatch`
- run daily using cron
- install dependencies
- execute the pipeline
- upload ranked results to Google Sheets
- store CSV outputs as workflow artifacts

Current schedule:

```text
0 6 * * *
```

GitHub Actions cron runs in UTC.

Required repository secrets:

- `GOOGLE_SHEET_ID`
- `GOOGLE_CREDENTIALS_JSON`
- `GROQ_API_KEY` if AI ranking is enabled

## Ranking Logic

The local ranker scores jobs using explainable signals, including:

- internship and stage keywords
- junior and entry-level signals
- role relevance
- must-have skills
- preferred stack matches
- nice-to-have technologies
- location fit
- freshness
- source quality
- seniority penalties
- experience requirement penalties

Optional Groq re-ranking can improve the ordering of the highest-ranked jobs. The final score is calculated as:

```text
final_score = 0.65 * ai_fit_score + 0.35 * local_fit_score
```

If AI ranking is disabled or a batch fails, the pipeline falls back to local ranking.

## Known Limitations

- Scraping sources may fail or change behavior over time
- Ranking rules are currently tuned to one candidate profile
- Some older MVP modules are still present but not used by `main.py`
- Automated tests are not yet included
- GitHub Actions depends on valid secrets and external API availability

## Roadmap

Planned improvements:

- Add tests for deduplication and ranking
- Align `config.yaml` with `local_ranker.py` internship keys
- Remove or archive unused MVP modules
- Add dashboard screenshots
- Add sample data for demo runs
- Move more ranking parameters into configuration

## Portfolio Value

This project demonstrates:

- web data collection
- data normalization and cleaning
- heuristic scoring
- LLM-assisted ranking
- CSV-based data workflows
- Google Sheets reporting
- CI/CD automation with GitHub Actions

It is practical, easy to explain, and useful as both a personal automation tool and a portfolio project.
