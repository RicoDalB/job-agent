from __future__ import annotations

import time
from typing import Any

import pandas as pd
import requests
from bs4 import BeautifulSoup


REMOTIVE_API_URL = "https://remotive.com/api/remote-jobs"

STANDARD_COLUMNS = [
    "title",
    "company",
    "location",
    "city",
    "state",
    "country",
    "is_remote",
    "job_type",
    "source",
    "date_posted",
    "salary",
    "min_amount",
    "max_amount",
    "currency",
    "interval",
    "apply_url",
    "company_url",
    "description",
    "search_role",
    "search_location",
]


def _as_list(value: Any) -> list:
    """Convert config values to a list safely."""
    if value is None:
        return []

    if isinstance(value, list):
        return value

    return [value]


def _empty_jobs_df() -> pd.DataFrame:
    """Return an empty DataFrame with the standard schema."""
    return pd.DataFrame(columns=STANDARD_COLUMNS)


def _strip_html(html: str | None) -> str:
    """Convert HTML job descriptions into clean readable text."""
    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator=" ", strip=True)

    return " ".join(text.split())


def _normalise_remotive_job(job: dict, search_term: str) -> dict:
    """Convert one Remotive job into our standard schema."""
    candidate_required_location = (
        job.get("candidate_required_location")
        or job.get("location")
        or "Remote"
    )

    description = _strip_html(job.get("description", ""))

    return {
        "title": job.get("title", "") or "",
        "company": job.get("company_name", "") or "",
        "location": candidate_required_location,
        "city": "",
        "state": "",
        "country": candidate_required_location,
        "is_remote": True,
        "job_type": job.get("category", "") or "",
        "source": "remotive",
        "date_posted": job.get("publication_date", "") or "",
        "salary": job.get("salary", "") or "",
        "min_amount": "",
        "max_amount": "",
        "currency": "",
        "interval": "",
        "apply_url": job.get("url", "") or "",
        "company_url": "",
        "description": description,
        "search_role": search_term,
        "search_location": "Remote",
    }


def fetch_remotive_jobs(config: dict) -> pd.DataFrame:
    """
    Fetch remote jobs from Remotive public API.

    The config block should look like:

    remotive:
      enabled: true
      search_terms:
        - "python"
        - "machine learning"
        - "data engineer"
      limit_per_search: 20
      delay_seconds: 3
    """
    remotive_config = config.get("remotive", {})

    enabled = bool(remotive_config.get("enabled", False))
    if not enabled:
        print("Remotive disabled in config")
        return _empty_jobs_df()

    search_terms = _as_list(remotive_config.get("search_terms", []))
    limit_per_search = int(remotive_config.get("limit_per_search", 20))
    delay_seconds = int(remotive_config.get("delay_seconds", 3))

    if not search_terms:
        print("No Remotive search terms configured")
        return _empty_jobs_df()

    all_rows = []

    for search_term in search_terms:
        print(f"Fetching Remotive jobs | search='{search_term}'")

        try:
            response = requests.get(
                REMOTIVE_API_URL,
                params={
                    "search": search_term,
                    "limit": limit_per_search,
                },
                timeout=30,
            )
            response.raise_for_status()

            payload = response.json()
            jobs = payload.get("jobs", [])

            print(f"Found {len(jobs)} Remotive jobs for '{search_term}'")

            for job in jobs:
                all_rows.append(
                    _normalise_remotive_job(
                        job=job,
                        search_term=search_term,
                    )
                )

        except requests.RequestException as error:
            print(f"Remotive request failed for '{search_term}'. Error: {error}")

        except ValueError as error:
            print(f"Could not parse Remotive response for '{search_term}'. Error: {error}")

        time.sleep(delay_seconds)

    if not all_rows:
        return _empty_jobs_df()

    return pd.DataFrame(all_rows, columns=STANDARD_COLUMNS)