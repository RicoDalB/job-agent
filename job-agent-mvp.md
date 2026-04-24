# Job Intelligence Agent — MVP Documentation

> An automated daily pipeline that scrapes job postings from LinkedIn, Indeed, Glassdoor and more, scores them against your profile using a free LLM, runs a CV gap analysis, and delivers ranked results to a Google Sheet every night. Zero cost. Fully automated.

---

## Table of contents

1. [Project overview](#1-project-overview)
2. [How it works — the big picture](#2-how-it-works--the-big-picture)
3. [Tech stack](#3-tech-stack)
4. [Prerequisites](#4-prerequisites)
5. [Account setup — step by step](#5-account-setup--step-by-step)
6. [Repository structure](#6-repository-structure)
7. [Configuration — `config.yaml`](#7-configuration--configyaml)
8. [Module breakdown](#8-module-breakdown)
9. [The AI agent — prompt engineering guide](#9-the-ai-agent--prompt-engineering-guide)
10. [Google Sheets output format](#10-google-sheets-output-format)
11. [GitHub Actions scheduler](#11-github-actions-scheduler)
12. [Weekend build plan](#12-weekend-build-plan)
13. [Known limitations and workarounds](#13-known-limitations-and-workarounds)
14. [How to present this project](#14-how-to-present-this-project)

---

## 1. Project overview

### What problem does this solve?

Job hunting is extremely time-consuming. The average job seeker manually checks multiple platforms daily, reads dozens of irrelevant listings, and never has a structured way to compare opportunities against their own profile. This project automates everything between "job gets posted" and "you decide whether to apply."

### What does the agent do?

Every night at a scheduled time, the agent automatically:

- Fetches all job postings published in the last 24 hours across LinkedIn, Indeed, Glassdoor, Google Jobs, Adzuna, and Remotive
- Removes duplicates across all sources
- Scores each posting from 0 to 100 based on how well it matches your defined preferences
- Compares each job description against your CV and identifies missing skills and keywords
- Generates one tailored CV bullet point per job that you could add to better fit that role
- Writes all enriched results to a Google Sheet, sorted by score descending
- Color-codes rows green (strong match), yellow (partial match), red (poor match)

### Why is this interesting as a portfolio project?

This project demonstrates end-to-end thinking that goes beyond individual skills. It involves data pipeline design, LLM prompt engineering, structured output parsing, API integration, and production deployment via CI/CD — all connected into a system that solves a real problem. It is immediately understandable to any interviewer, regardless of their technical background, and it is genuinely useful to you personally, which makes it easy to discuss authentically.

---

## 2. How it works — the big picture

The pipeline runs in five sequential phases every night.

**Phase 1 — Fetch**
Multiple job sources are queried concurrently. `python-jobspy` handles LinkedIn, Indeed, Glassdoor, and Google Jobs in a single function call. Adzuna and Remotive are called separately via their REST APIs. All results are collected into a unified data structure.

**Phase 2 — Clean**
All job postings from all sources are merged. Duplicates are identified by hashing the combination of company name and job title. Only postings from the last 24 hours are kept. The result is a clean, unique list of today's relevant jobs.

**Phase 3 — Score**
Each job description is sent to the Groq API along with your preference profile. The LLM returns a structured JSON response containing a numerical fit score, a one-sentence verdict, matched skills, and any red flags. This is Prompt 1.

**Phase 4 — Analyse**
Each job description is sent to the Groq API again, this time alongside the text extracted from your CV PDF. The LLM returns a structured JSON response with missing skills, keywords to add, and an overall CV fit percentage. It also generates one tailored bullet point you could add to your CV for that specific role. This is Prompt 2 and Prompt 3.

**Phase 5 — Output**
All enriched job data is written as new rows in your Google Sheet. The sheet is sorted by fit score. Conditional formatting makes the top opportunities immediately visible.

---

## 3. Tech stack

Every tool in this stack is free. No credit card is required for any of them.

### Scraping layer

| Tool | Purpose | Cost | Notes |
|---|---|---|---|
| `python-jobspy` | Scrape LinkedIn, Indeed, Glassdoor, Google Jobs | Free | One pip install, one function call |
| Adzuna REST API | Additional job listings, strong EU coverage | Free | Requires a free API key from their developer portal |
| Remotive REST API | Remote-first tech jobs | Free | No key required, public endpoint |

`python-jobspy` is an open-source Python library that handles all the complexity of scraping major job boards. It manages pagination, rate limiting, HTML parsing, and data normalization internally. You do not write any scraping code. You call one function with your search parameters and receive a clean pandas DataFrame.

### AI layer

| Tool | Purpose | Cost | Notes |
|---|---|---|---|
| Groq API | LLM inference for scoring and analysis | Free | Free tier includes ~500,000 tokens/day |
| Llama 3.3 70B | The model running on Groq | Free | Open-source model hosted by Groq |
| `pdfplumber` | Extract text from your CV PDF | Free | Python library, no API needed |

Groq is an AI inference platform that runs open-source models on custom hardware. The free tier gives you access to Llama 3.3 70B — a 70-billion-parameter model that performs at a high level on structured reasoning tasks. For a personal pipeline processing around 50 jobs per night, you will use roughly 5,000–10,000 tokens total per run, which is well within the daily free limit.

### Output and orchestration

| Tool | Purpose | Cost | Notes |
|---|---|---|---|
| `gspread` | Write results to Google Sheets | Free | Python library for Sheets API |
| Google Sheets | Store and view results | Free | Formatted with conditional coloring |
| GitHub Actions | Schedule and run the pipeline nightly | Free | 2,000 free minutes/month on free accounts |
| GitHub Secrets | Store API keys securely | Free | Built into every GitHub repository |

---

## 4. Prerequisites

Before starting, make sure you have the following installed and ready on your machine.

### Required software

- **Python 3.11 or newer** — the pipeline is written in Python. Older versions may have compatibility issues with some libraries.
- **Git** — for version control and for triggering GitHub Actions.
- **A code editor** — VS Code is recommended but any editor works.
- **pip** — Python's package manager, comes bundled with Python.

### Required accounts

You will need to create free accounts on the following platforms. None of them require a credit card.

- **GitHub** — to host the repository and run the scheduled Actions workflow
- **Groq** — to access the free LLM API (console.groq.com)
- **Adzuna Developer** — to get a free API key for job listings (developer.adzuna.com)
- **Google Cloud** — to create a service account for the Sheets API (console.cloud.google.com)

### Required files

- **Your CV as a PDF** — the CV analyser extracts text from this file and compares it against each job description. Keep it updated.

---

## 5. Account setup — step by step

This section walks through every external account and credential you need to configure before writing a single line of code.

### 5.1 Groq API key

1. Go to console.groq.com and sign up with your email. No credit card is required.
2. Once logged in, navigate to the API Keys section in the left sidebar.
3. Click "Create API Key" and give it a name like `job-agent`.
4. Copy the key immediately — it will not be shown again.
5. Store it temporarily in a safe place. You will add it to GitHub Secrets later.

**Rate limits to know:** On the free tier, Llama 3.3 70B allows approximately 30 requests per minute and 500,000 tokens per day. Your nightly run will send roughly 2–3 API calls per job (scoring + analysis + bullet). For 50 jobs this is around 100–150 requests, well within limits, but spread them out with small delays to be safe.

### 5.2 Adzuna API credentials

1. Go to developer.adzuna.com and click "Register".
2. Fill in the registration form. Free tier access is instant.
3. After logging in, create a new application from the dashboard.
4. Copy both the `App ID` and the `App Key`.
5. Note that Adzuna requires you to specify a country code in the API URL. For Italy use `it`, for general European searches use `gb` (UK) or `de` (Germany) which have the most listings.

### 5.3 Google Sheets service account

This is the most involved setup but it only needs to be done once.

1. Go to console.cloud.google.com and create a new project. Name it something like `job-agent`.
2. In the search bar at the top, search for "Google Sheets API" and click Enable.
3. Also search for "Google Drive API" and click Enable (required for `gspread` to work).
4. In the left sidebar, go to IAM & Admin → Service Accounts.
5. Click "Create Service Account". Give it a name like `job-agent-writer`. Click Create.
6. Skip the optional permission steps and click Done.
7. Click on the service account you just created, then go to the Keys tab.
8. Click "Add Key" → "Create new key" → choose JSON → click Create.
9. A JSON file will download automatically. This file contains your credentials. Keep it safe and never commit it to a public repository.
10. Create a new Google Sheet at sheets.google.com. Name it `Job Agent Results`.
11. Share the sheet with the service account email address (found in the JSON file under `client_email`). Give it Editor permissions.
12. Copy the sheet ID from the URL — it is the long string between `/d/` and `/edit`.

### 5.4 GitHub repository and secrets

1. Create a new private GitHub repository named `job-agent`.
2. Go to Settings → Secrets and variables → Actions.
3. Click "New repository secret" and add the following secrets:

| Secret name | Value |
|---|---|
| `GROQ_API_KEY` | Your Groq API key |
| `ADZUNA_APP_ID` | Your Adzuna App ID |
| `ADZUNA_APP_KEY` | Your Adzuna App Key |
| `GOOGLE_CREDENTIALS_JSON` | The entire contents of your Google service account JSON file |
| `GOOGLE_SHEET_ID` | The ID of your Google Sheet |

Secrets stored here are encrypted and injected as environment variables when GitHub Actions runs your workflow. They are never visible in logs.

---

## 6. Repository structure

```
job-agent/
│
├── README.md                     — project overview and quick start
├── config.yaml                   — your search preferences (roles, locations, skills)
├── cv.pdf                        — your CV (add to .gitignore if repo is public)
├── requirements.txt              — all Python dependencies
├── .gitignore                    — excludes cv.pdf, .env, credentials files
│
├── main.py                       — entry point; orchestrates all phases
│
├── scraper/
│   ├── __init__.py
│   ├── jobspy_fetch.py           — fetches from LinkedIn, Indeed, Glassdoor, Google
│   ├── adzuna_fetch.py           — fetches from Adzuna REST API
│   ├── remotive_fetch.py         — fetches from Remotive public API
│   └── dedup.py                  — merges all sources and removes duplicates
│
├── agent/
│   ├── __init__.py
│   ├── cv_parser.py              — extracts clean text from cv.pdf using pdfplumber
│   ├── scorer.py                 — Prompt 1: relevance score against your preferences
│   ├── cv_analyser.py            — Prompt 2: gap analysis between job and CV
│   └── bullet_gen.py             — Prompt 3: one tailored CV bullet per job
│
├── output/
│   ├── __init__.py
│   └── sheets_writer.py          — authenticates with gspread and writes rows
│
└── .github/
    └── workflows/
        └── nightly.yml           — cron schedule and GitHub Actions configuration
```

Each folder has a single clear responsibility. The `scraper/` folder knows nothing about the AI layer. The `agent/` folder knows nothing about where data came from. The `output/` folder only knows how to write to Sheets. `main.py` connects them all in sequence. This separation makes each module easy to test, debug, and replace independently.

---

## 7. Configuration — `config.yaml`

All your personal preferences live in a single YAML file. You should not need to touch Python files to change what the agent searches for.

### What belongs in config.yaml

**Search terms** — the job titles you are targeting. Be specific. Generic terms like "engineer" will return thousands of irrelevant results. Good examples for an AI Master's student: `data engineer`, `ML engineer`, `AI engineer`, `data scientist`, `MLOps engineer`, `backend engineer Python`.

**Locations** — cities or regions you are open to. You can include `remote` as a location to catch remote-first roles. If you are open to relocation, list multiple cities.

**Must-have skills** — the minimum skills a job must mention to be worth considering. These anchor the scoring prompt. Examples: `Python`, `SQL`, `machine learning`.

**Preferred stack** — technologies you know and enjoy working with. The scorer will reward jobs that match these. Examples: `PyTorch`, `Apache Spark`, `dbt`, `Airflow`, `Docker`, `Kubernetes`.

**Nice-to-have** — secondary preferences that boost the score but are not required. Examples: `remote-friendly`, `startup`, `equity compensation`.

**Exclusions** — terms that should drop a job's score significantly or filter it out entirely. Examples: `Java`, `COBOL`, `senior` (if you are not targeting senior roles), `10 years experience`.

**Results per source** — how many jobs to pull from each platform per search term per run. Start with 25–50. Higher numbers increase runtime and token usage.

**Score threshold** — the minimum score a job must receive to appear in the green section of the sheet. Suggested starting value: 70.

### Why keep this separate from code

The config file is the only thing you should need to edit regularly. As your job search evolves — new cities, new tech preferences, different seniority targets — you update one file. No code changes required. This is also good engineering practice: separating configuration from logic.

---

## 8. Module breakdown

### 8.1 `scraper/jobspy_fetch.py`

This module is deliberately minimal. `python-jobspy` does all the heavy lifting. Your job is to:

- Read the search terms and locations from `config.yaml`
- Call `scrape_jobs()` with the right parameters, including `hours_old=24` to only get today's postings and `linkedin_fetch_description=True` to get full job descriptions (needed for AI analysis)
- Return the results as a pandas DataFrame

The library handles rate limiting, user agent rotation, HTML parsing, and field normalization across all platforms internally. Do not write your own scraping logic — it is not necessary and it is fragile.

### 8.2 `scraper/adzuna_fetch.py`

Adzuna's API is RESTful and very straightforward. You construct a URL with your App ID, App Key, search term, location, and a date filter parameter to get only recent postings. The response is JSON. Parse it into the same DataFrame format that `jobspy_fetch.py` produces so that the dedup step can treat all sources uniformly.

Important Adzuna detail: the API returns only a snippet of the job description by default, not the full text. The snippet is usually enough for scoring, but for gap analysis you may need to fetch the full job page separately. For the MVP, the snippet is fine.

### 8.3 `scraper/remotive_fetch.py`

Remotive's API requires no authentication. You send a GET request to their public endpoint with a `search` parameter for your keyword and optionally a `category` parameter. The response includes a full job description in HTML format. Strip the HTML tags before passing the text to the AI layer.

Remotive is particularly valuable because it focuses entirely on remote tech roles. Even if you are in Italy, remote positions from global companies are highly relevant and often overlooked on traditional job boards.

### 8.4 `scraper/dedup.py`

This module receives a list of DataFrames (one per source) and must produce a single clean DataFrame. The deduplication logic should:

1. Normalize company names (lowercase, strip whitespace, remove punctuation) before comparison
2. Normalize job titles similarly
3. Hash the combined `normalized_company + normalized_title` string
4. Drop any row whose hash has already been seen
5. Drop any row where `date_posted` is older than 24 hours

The output of this module is the single DataFrame that flows into the agent layer. It should have a consistent schema regardless of which source each job came from: title, company, location, salary range, job type, apply URL, description, source platform, date posted.

### 8.5 `agent/cv_parser.py`

This module has one job: take `cv.pdf` and return a clean string of text. `pdfplumber` opens the PDF page by page and extracts all text content. After extraction, clean the text by removing excessive whitespace, stripping non-ASCII characters that add noise, and joining all pages into one continuous block.

The resulting CV text will be injected into the prompts for gap analysis. Keep the parser output consistent — if the text changes format between runs, your prompts may produce inconsistent results.

Store the parsed CV text in memory at the start of the run so you only read the file once, then reuse the string across all jobs.

### 8.6 `agent/scorer.py`

This is the first and most important AI module. For each job posting, it asks the LLM a single question: how well does this job match this candidate's preferences?

The prompt must be structured so that the LLM returns a response that can be reliably parsed as JSON. The score should be a number from 0 to 100. The verdict should be a single sentence. The matched skills and red flags should be arrays.

Invest time in prompt engineering here. The quality of your scoring prompt determines the usefulness of the entire system. Test it manually on 10 jobs before wiring it into the pipeline. Ask yourself: does a score of 85 actually feel like a strong match? Does a score of 30 feel irrelevant? Adjust the prompt language until the numbers match your intuition.

Tips for a better scoring prompt:
- Be explicit about what constitutes a high score versus a low score
- Tell the model to weight must-have skills more heavily than nice-to-have ones
- Ask it to penalize roles that require significantly more experience than you have
- Ask it to reward roles that explicitly mention your target domain (e.g., machine learning, data engineering)

### 8.7 `agent/cv_analyser.py`

This module compares the job description against your actual CV text and identifies the gap. The output should be immediately actionable: not just "you are missing Python" (you probably are not) but "this role requires experience with Spark Streaming and your CV does not mention real-time data processing."

The prompt for this module sends both documents to the LLM and asks for a structured comparison. The key output fields are:

- **Missing skills** — things the job requires that your CV does not demonstrate
- **Keywords to add** — specific terms from the job description that should appear in your CV for ATS (applicant tracking system) matching
- **Transferable strengths** — things you have that are relevant but may not be framed in the job's language
- **CV fit percentage** — a separate metric from the job score; this measures specifically how well your CV as a document would perform for this role

The distinction between the score (from `scorer.py`) and the CV fit percentage (from `cv_analyser.py`) is intentional. A job can be a strong match for your interests (high score) but your CV may not be well-positioned for it (low fit). This distinction is useful — it tells you when to update your CV before applying.

### 8.8 `agent/bullet_gen.py`

This is the most practical output of the entire system. For each job, the model generates one new CV bullet point you could add to your experience section to better match that specific role.

A good bullet point starts with an action verb, is quantified where possible, and uses the language and keywords from the job description. The prompt should instruct the model to write something consistent with your existing experience — it should not invent things you have not done, but it should reframe what you have done in terms the hiring manager will recognize.

This module is fast to build and produces immediately usable output. It is also one of the most impressive things to demo in an interview — you can show the recruiter a live sheet where each job has a tailored bullet point ready to copy into your CV.

### 8.9 `output/sheets_writer.py`

This module authenticates with the Google Sheets API using your service account credentials, finds or creates the correct sheet, and appends a new batch of rows for today's run.

Design the writer so it does not overwrite previous runs. Each morning you open the sheet and see only today's results at the top, with previous days still accessible below. Use a date header row to separate runs visually.

The column order matters for readability. Suggested order: Date, Score, Verdict, Title, Company, Location, Salary, Remote, Source, Apply URL, Missing Skills, Keywords to Add, CV Fit %, Generated Bullet Point.

---

## 9. The AI agent — prompt engineering guide

Prompt engineering is the core skill this project exercises. This section explains the principles behind each prompt so you can build them confidently and iterate on them effectively.

### General principles

**Always request JSON output.** Every prompt in this pipeline should instruct the model to respond only with valid JSON. This makes parsing reliable and removes the need to handle unstructured text. Include a precise JSON schema in every prompt so the model knows exactly what structure to produce.

**Provide clear evaluation criteria.** The model does not know what a "good match" means to you unless you tell it. Be specific: "A score above 80 means the role matches at least 4 of my 5 must-have skills and does not require more than 5 years of experience."

**Control the output length.** For scoring prompts, set `max_tokens` to around 300. For analysis prompts, around 500. For bullet point generation, around 100. Shorter outputs cost fewer tokens, run faster, and tend to be more focused.

**Truncate the inputs.** Job descriptions vary enormously in length. Some are 200 words, others are 2,000. Truncate all descriptions to a consistent character limit (around 2,500–3,000 characters) before injecting them into prompts. This keeps token usage predictable and prevents the model from going over the context window.

**Test before automating.** Before connecting any prompt to the live pipeline, test it manually in the Groq playground or by running a small script against 10 real job descriptions. Read the outputs carefully. Adjust the wording until the outputs consistently match your expectations. Only then wire it into `main.py`.

### Prompt 1 — relevance scorer

The goal is a number that reflects genuine fit, not just keyword overlap. The prompt should include:

- Your full preferences profile (roles, stack, must-haves, location, seniority level)
- The job title and full description
- A clear instruction to return only JSON in a specified schema
- Explicit guidance on what makes a score high versus low
- An instruction to be critical rather than generous — it is more useful to underestimate than overestimate fit

### Prompt 2 — CV gap analyser

The goal is a structured comparison between two documents. The prompt should include:

- The full job description (truncated)
- Your full CV text (truncated to around 2,000 characters)
- An instruction to identify gaps, not just list requirements
- An instruction to distinguish between hard gaps (you do not have the skill) and soft gaps (you have a related skill but have not framed it correctly)
- The JSON schema with the four output fields described in section 8.7

### Prompt 3 — bullet point generator

The goal is one immediately usable sentence. The prompt should include:

- A brief context about your background (extract the first 500 characters of your CV)
- The job description (truncated)
- An explicit instruction that the bullet must be consistent with your real experience
- A length constraint (maximum 25 words)
- An instruction to start with a past-tense action verb
- An instruction to use at least one specific technology or metric from the job description

### Handling JSON parsing failures

LLMs occasionally produce malformed JSON — extra text before the opening brace, trailing commas, unescaped quotes. Build error handling around every JSON parse call. If parsing fails, log the raw output and skip that job rather than crashing the entire run. After the first week of operation, review your error logs to see if any prompts consistently fail and adjust the wording accordingly.

---

## 10. Google Sheets output format

### Column definitions

| Column | Source | Notes |
|---|---|---|
| Run date | System | The date the pipeline ran |
| Score | scorer.py | Integer 0–100 |
| Verdict | scorer.py | One sentence from the LLM |
| Title | Job data | Normalized job title |
| Company | Job data | Company name |
| Location | Job data | City or Remote |
| Salary | Job data | Range if available, blank if not |
| Remote | Job data | Yes / No / Hybrid |
| Job type | Job data | Full-time / Contract / etc. |
| Source | Scraper | LinkedIn / Indeed / Adzuna / etc. |
| Posted | Job data | Date posted |
| Apply URL | Job data | Direct link to job posting |
| Missing skills | cv_analyser.py | Comma-separated list |
| Keywords to add | cv_analyser.py | Comma-separated list |
| CV fit % | cv_analyser.py | Integer 0–100 |
| Generated bullet | bullet_gen.py | Ready-to-use CV bullet point |

### Conditional formatting

Set up three color bands in Google Sheets using conditional formatting rules on the Score column:

- **Green background** (e.g., rows where Score ≥ 75) — strong match, review these first
- **Yellow background** (e.g., rows where Score is 50–74) — potential match, worth a quick look
- **No highlighting** (rows where Score < 50) — weak match, skip unless nothing better exists

Sort the sheet by Score descending on each run so the strongest matches always appear at the top.

### Protecting previous runs

Each nightly run should insert rows at the top of the sheet above a separator row, not overwrite the entire sheet. This lets you scroll down to see previous days. It also lets you add a column for personal notes (e.g., "applied", "not interested", "interviewed") without losing them when the next run writes new data.

---

## 11. GitHub Actions scheduler

### What GitHub Actions does for this project

GitHub Actions is a CI/CD platform built into GitHub. You write a YAML file that describes what to run and when. GitHub provides a virtual machine (Ubuntu Linux) that executes your script on their servers. This means the pipeline runs even when your laptop is off, which is the whole point.

The free tier gives GitHub accounts 2,000 compute minutes per month. A single pipeline run takes roughly 3–5 minutes. Running nightly for 30 days costs around 90–150 minutes, well within the free allowance.

### Workflow file structure

The workflow file lives at `.github/workflows/nightly.yml`. It contains three main sections:

**Trigger** — defines when the workflow runs. For this project, you need two triggers: a scheduled cron expression for the nightly run, and a manual trigger (`workflow_dispatch`) so you can test the full pipeline without waiting for the scheduled time.

**Environment** — defines the runtime environment. Use `ubuntu-latest` as the operating system. Specify Python 3.11. Install all dependencies from `requirements.txt`.

**Steps** — the sequence of actions. Check out the repository, set up Python, install dependencies, write the Google credentials to a file from the secret, and then run `python main.py`.

### Cron schedule

GitHub Actions uses UTC time. If you are in Italy (UTC+2 in summer, UTC+1 in winter), a cron of `0 19 * * *` will run the pipeline at 9pm Italian time in summer and 8pm in winter. Adjust to your preference.

### Secrets injection

The secrets you stored in GitHub (from section 5.4) are available inside the workflow as environment variables. You reference them in the workflow YAML and they are automatically available to your Python script via `os.environ`. The Google credentials JSON is the most complex because it is a multi-line JSON object — write it to a temporary file at the start of the workflow step and point `gspread` to that file path.

### Monitoring runs

After pushing your workflow file, go to the Actions tab in your GitHub repository. Each run appears as a line with a green checkmark (success) or red X (failure). Click any run to see the full log output, which includes print statements from your Python code. Use this for debugging in the first week of operation.

---

## 12. Weekend build plan

This plan assumes you work roughly eight hours on Saturday and six hours on Sunday.

### Saturday — foundation and scraping

**Morning session (3 hours)**

Start by completing all account setup from section 5. Do this before touching any code. The most time-consuming parts are the Google Cloud service account setup and sharing the Sheet. Getting stuck on credentials mid-afternoon is frustrating and avoidable.

Once all accounts are ready, create the GitHub repository, clone it locally, set up a Python virtual environment, and install all required libraries. Create the config.yaml file with your actual preferences. Add your CV PDF to the project root. Create a .gitignore file that excludes the CV and any credentials files.

End of morning goal: you can run `python -c "import jobspy; import groq; import gspread; print('all good')"` without errors.

**Afternoon session (3 hours)**

Build the scraping layer. Start with `jobspy_fetch.py` because it produces the most results with the least code. Run it against one search term and one location, print the DataFrame, and verify that you are getting real job postings with descriptions.

Then build `adzuna_fetch.py` and `remotive_fetch.py`. Focus on getting the same fields out of each source rather than getting every possible field. Consistency matters more than completeness at this stage.

Finish the afternoon with `dedup.py`. Merge all three sources, deduplicate, and filter by date. Print the size of the resulting DataFrame.

End of afternoon goal: running the scraper produces a clean DataFrame of today's unique job postings from all sources.

**Evening session (2 hours)**

Build `sheets_writer.py`. Authenticate with gspread, open your sheet, and write a test row. If you can see that test row appear in the Google Sheet, the hardest infrastructure piece is done.

Wire the scraper and writer together in `main.py` so that running `python main.py` fetches jobs and writes them to the sheet. This is your working pipeline before the AI layer.

End of Saturday: a working automated scraper that writes to Google Sheets. No AI yet, but the plumbing is complete.

### Sunday — building the AI agent

**Morning session (3 hours)**

Build `cv_parser.py` first. Open your CV PDF, extract the text, print it, and verify it looks clean and readable. Fix any extraction issues (encoding problems, garbled text from scanned PDFs).

Spend the majority of this session on `scorer.py`. Write the prompt, then test it manually by calling the Groq API against five different job descriptions from your Saturday results. Read each output carefully. Does the score make sense? Does the verdict capture why? Iterate on the prompt until you are satisfied. This is the core intellectual work of the project — take your time.

**Late morning to early afternoon (2 hours)**

Build `cv_analyser.py`. The same iterative approach: write the prompt, test against real job descriptions with your real CV text, read the outputs, adjust. Pay particular attention to whether the "missing skills" section is genuinely useful or just repeating every skill in the job description.

Build `bullet_gen.py`. This tends to work well on the first or second attempt. Test it on five jobs and read the generated bullets. They should feel like something you could actually put in your CV.

**Afternoon session (2 hours)**

Wire all three agent modules into `main.py`. The flow is: for each job in the cleaned DataFrame, call the scorer, call the analyser, call the bullet generator, collect all outputs, and pass everything to the sheets writer as one enriched row.

Add a small delay between API calls to avoid rate limiting. Add error handling around all JSON parsing. Run the full pipeline end-to-end locally and inspect the sheet.

**Evening session (1 hour)**

Create `.github/workflows/nightly.yml`. Push the complete project to GitHub. Go to the Actions tab and trigger a manual run using `workflow_dispatch`. Watch the logs. Fix any issues with environment variables or file paths that behave differently on GitHub's Ubuntu environment versus your local machine.

Once the manual run succeeds and writes results to your sheet, the project is done.

End of Sunday: a fully automated AI agent running in production.

---

## 13. Known limitations and workarounds

### LinkedIn rate limiting

LinkedIn is the most aggressive platform in terms of rate limiting. `python-jobspy` handles this better than raw scraping, but you may still occasionally receive empty results or 429 errors from LinkedIn specifically. The workaround is to add a random delay of 2–5 seconds between LinkedIn search pages and to keep your `results_wanted` parameter reasonable (25–50 per run). If LinkedIn blocks your GitHub Actions IP, the other sources (Indeed, Glassdoor, Adzuna, Remotive) still provide strong coverage.

### Indeed full descriptions

`python-jobspy` returns Indeed job descriptions, but they may be truncated in some cases. For the scoring prompt this is usually fine. For the CV analyser, a truncated description means the gap analysis may miss some requirements. This is an acceptable limitation for an MVP.

### Groq token limits

The free Groq tier resets daily. If you run the pipeline more than once per day (e.g., during testing), you may exhaust the daily token budget. To avoid this during development, test the AI modules against a sample of 5–10 jobs rather than the full daily pull.

### Google Sheets API quota

The Google Sheets API has a per-minute write quota. If your pipeline writes more than 60 requests per minute, it will start returning errors. Write all rows for a single run in one batch call rather than one row at a time. `gspread` supports batch appending.

### HTML in job descriptions

Remotive returns job descriptions in HTML format. Some Indeed descriptions also contain HTML tags. Always strip HTML before sending text to the LLM — the tags add tokens without adding information and can confuse the model's parsing.

### CV PDF quality

`pdfplumber` works best with digitally-created PDFs. If your CV was scanned or saved from a poorly formatted tool, the extracted text may be fragmented or garbled. Open your CV in a text editor after extraction and verify it reads cleanly. If there are issues, consider exporting your CV from Word or Google Docs as a fresh PDF.

---

## 14. How to present this project

### In interviews

When asked about personal projects or automation, the most effective framing is outcome-first: "I built a system that runs every night, pulls from LinkedIn, Indeed, Glassdoor, and three other sources, and gives me a prioritized shortlist of today's relevant jobs with a gap analysis against my CV — all in a Google Sheet I check each morning."

This leads naturally to interesting follow-up questions about the technical decisions you made. Be ready to discuss why you chose Groq over local models (inference as a service, zero cost, no GPU required), how you handle structured output from the LLM (JSON schema in the prompt, error handling around parsing), and what you learned from prompt engineering (the scoring prompt required five iterations to produce calibrated scores).

### On your CV

A bullet point for this project might read: "Built an automated job intelligence pipeline that fetches from 6 sources via API, scores postings against a candidate profile using LLM inference on Groq, and performs CV gap analysis — reducing daily job search review time by over 80%."

If you have a GitHub link to show, make sure the README is well-written and the project structure is clean before sharing it.

### What makes it impressive technically

The parts of this project that demonstrate real engineering thinking are not the scraping (that is one library call) but the design decisions around it: the clean separation of the scraping layer from the agent layer, the use of structured JSON outputs from the LLM with robust error handling, the prompt engineering methodology (iterative testing against real data), and the deployment of a production-grade cron pipeline via GitHub Actions. These are things that separate someone who "built a chatbot" from someone who built a production AI system.

---

*Built with `python-jobspy`, `groq`, `pdfplumber`, `gspread`, and GitHub Actions. Total monthly cost: €0.*
