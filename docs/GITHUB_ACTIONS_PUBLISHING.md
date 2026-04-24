# GitHub Actions Publishing Guide

This guide explains how to run the project automatically with GitHub Actions and publish the final ranked jobs to Google Sheets.

## What The Workflow Does

The workflow in `.github/workflows/publish.yml`:

1. checks out the repository
2. installs Python
3. installs the project dependencies
4. runs `python main.py`
5. runs `python scripts/upload_ranked_csv_to_sheets.py`
6. stores the generated CSV files as workflow artifacts

## Required Secrets

Add the following repository secrets:

- `GROQ_API_KEY`
- `GOOGLE_SHEET_ID`
- `GOOGLE_CREDENTIALS_JSON`

`GOOGLE_CREDENTIALS_JSON` must contain the full JSON content of your Google service account key.

## Google Sheets Setup

Before the workflow can publish successfully:

1. Create a Google Cloud service account.
2. Enable Google Sheets API and Google Drive API.
3. Download the service account JSON key.
4. Share your target spreadsheet with the service account email.
5. Copy the spreadsheet ID into the `GOOGLE_SHEET_ID` secret.

## Manual Run

You can run the workflow manually from the GitHub Actions tab using `workflow_dispatch`.

This is useful for:

- testing secrets
- checking Sheets permissions
- validating new search settings
- debugging workflow changes

## Scheduled Run

The workflow includes a daily cron schedule.

Current schedule:

- `0 6 * * *`

GitHub cron expressions use UTC, so `06:00 UTC` is not the same as local Italian time all year.

If you want the run closer to morning in Italy, adjust the cron value based on daylight saving time expectations.

## How To Customize It

Common customizations:

- change the cron schedule
- change the Python version
- disable AI ranking in `config.yaml`
- add another artifact path if you want to keep historical files

## Failure Modes To Expect

Typical workflow failures are:

- missing `GROQ_API_KEY`
- wrong or expired Google service account JSON
- spreadsheet not shared with the service account
- scraping source instability from external job providers

If the pipeline finishes but the publishing step fails, inspect:

- GitHub Actions logs
- worksheet names from `config.yaml`
- Google sharing permissions

## Suggested Publication Story

If you want to present this project on GitHub or LinkedIn, describe the workflow as:

"An automated job discovery and ranking pipeline that collects fresh listings, filters duplicates, scores opportunities against a candidate profile, and publishes a clean dashboard to Google Sheets on a schedule."
