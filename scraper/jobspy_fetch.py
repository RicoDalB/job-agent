from __future__ import annotations

import time
from typing import Any

import pandas as pd
from jobspy import scrape_jobs


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


DEFAULT_SAFE_SITES = [
    "indeed",
    "linkedin",
    "google",
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


def _get_value(row: pd.Series, column: str, default: Any = None) -> Any:
    """Safely get a value from a pandas row."""
    if column not in row:
        return default

    value = row[column]

    if pd.isna(value):
        return default

    return value


def _build_location(row: pd.Series) -> str:
    """Create a readable location string."""
    location = _get_value(row, "location")

    if location:
        return str(location)

    parts = [
        _get_value(row, "city"),
        _get_value(row, "state"),
        _get_value(row, "country"),
    ]

    parts = [str(part) for part in parts if part]

    return ", ".join(parts)


def _build_salary(row: pd.Series) -> str:
    """Create a readable salary string from JobSpy salary fields."""
    min_amount = _get_value(row, "min_amount")
    max_amount = _get_value(row, "max_amount")
    currency = _get_value(row, "currency")
    interval = _get_value(row, "interval")

    if min_amount is None and max_amount is None:
        return ""

    if min_amount is not None and max_amount is not None:
        salary = f"{min_amount} - {max_amount}"
    elif min_amount is not None:
        salary = f"From {min_amount}"
    else:
        salary = f"Up to {max_amount}"

    if currency:
        salary = f"{salary} {currency}"

    if interval:
        salary = f"{salary} / {interval}"

    return salary


def _normalise_jobspy_dataframe(
    jobs: pd.DataFrame,
    search_role: str,
    search_location: str,
) -> pd.DataFrame:
    """
    Convert raw JobSpy output into our standard schema.
    """
    if jobs is None or jobs.empty:
        return _empty_jobs_df()

    df = jobs.copy()
    df.columns = [str(column).lower().strip() for column in df.columns]

    rows = []

    for _, row in df.iterrows():
        source = _get_value(row, "site", "")
        apply_url = _get_value(row, "job_url", "")

        job_url_direct = _get_value(row, "job_url_direct", "")
        if job_url_direct:
            apply_url = job_url_direct

        normalised_row = {
            "title": _get_value(row, "title", ""),
            "company": _get_value(row, "company", ""),
            "location": _build_location(row),
            "city": _get_value(row, "city", ""),
            "state": _get_value(row, "state", ""),
            "country": _get_value(row, "country", ""),
            "is_remote": _get_value(row, "is_remote", ""),
            "job_type": _get_value(row, "job_type", ""),
            "source": source,
            "date_posted": _get_value(row, "date_posted", ""),
            "salary": _build_salary(row),
            "min_amount": _get_value(row, "min_amount", ""),
            "max_amount": _get_value(row, "max_amount", ""),
            "currency": _get_value(row, "currency", ""),
            "interval": _get_value(row, "interval", ""),
            "apply_url": apply_url,
            "company_url": _get_value(row, "company_url", ""),
            "description": _get_value(row, "description", ""),
            "search_role": search_role,
            "search_location": search_location,
        }

        rows.append(normalised_row)

    return pd.DataFrame(rows, columns=STANDARD_COLUMNS)


def _build_google_search_term(role: str, location: str) -> str:
    """
    Google Jobs works better with a very explicit query.
    """
    return f"{role} jobs near {location} since yesterday"


def _scrape_single_site(
    site_name: str,
    role: str,
    location: str,
    results_wanted: int,
    hours_old: int,
    distance: int,
    country_indeed: str,
    linkedin_fetch_description: bool,
    verbose: int,
) -> pd.DataFrame:
    """
    Scrape one site only.

    Calling one site at a time prevents a broken source from killing
    the entire search.
    """
    print(
        f"Fetching JobSpy jobs | site='{site_name}' "
        f"| role='{role}' | location='{location}'"
    )

    scrape_kwargs = {
        "site_name": [site_name],
        "search_term": role,
        "location": location,
        "results_wanted": results_wanted,
        "hours_old": hours_old,
        "distance": distance,
        "description_format": "markdown",
        "verbose": verbose,
    }

    if site_name in ["indeed", "glassdoor"]:
        scrape_kwargs["country_indeed"] = country_indeed

    if site_name == "linkedin":
        scrape_kwargs["linkedin_fetch_description"] = linkedin_fetch_description

    if site_name == "google":
        scrape_kwargs["google_search_term"] = _build_google_search_term(
            role=role,
            location=location,
        )

    raw_jobs = scrape_jobs(**scrape_kwargs)

    clean_jobs = _normalise_jobspy_dataframe(
        jobs=raw_jobs,
        search_role=role,
        search_location=location,
    )

    print(f"Found {len(clean_jobs)} jobs from {site_name}")

    return clean_jobs


def fetch_jobspy_jobs(config: dict) -> pd.DataFrame:
    """
    Fetch jobs using python-jobspy.

    Recommended sites for this project:
    - indeed
    - linkedin
    - google

    Avoid using JobSpy's default all-sites behavior in Europe because
    several sources can fail, be blocked, or crash the full scrape.
    """
    search_config = config.get("search", {})

    roles = _as_list(search_config.get("roles"))
    locations = _as_list(search_config.get("locations"))

    site_names = search_config.get("jobspy_sites", DEFAULT_SAFE_SITES)
    site_names = _as_list(site_names)

    results_wanted = int(search_config.get("results_per_source", 10))
    hours_old = int(search_config.get("hours_old", 72))
    distance = int(search_config.get("distance", 50))
    country_indeed = search_config.get("country_indeed", "Italy")
    verbose = int(search_config.get("verbose", 1))
    delay_seconds = int(search_config.get("delay_seconds", 2))

    linkedin_fetch_description = bool(
        search_config.get("linkedin_fetch_description", False)
    )

    all_results = []

    for role in roles:
        for location in locations:
            for site_name in site_names:
                try:
                    clean_jobs = _scrape_single_site(
                        site_name=site_name,
                        role=role,
                        location=location,
                        results_wanted=results_wanted,
                        hours_old=hours_old,
                        distance=distance,
                        country_indeed=country_indeed,
                        linkedin_fetch_description=linkedin_fetch_description,
                        verbose=verbose,
                    )

                    if not clean_jobs.empty:
                        all_results.append(clean_jobs)

                except Exception as error:
                    print(
                        f"JobSpy failed | site='{site_name}' "
                        f"| role='{role}' | location='{location}' "
                        f"| error={error}"
                    )

                time.sleep(delay_seconds)

    if not all_results:
        return _empty_jobs_df()

    return pd.concat(all_results, ignore_index=True)