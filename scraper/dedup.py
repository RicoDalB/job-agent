from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd


def _normalise_text(value: Any) -> str:
    """
    Normalize text for duplicate detection.
    Example: 'Machine Learning Engineer - Stage' and 'machine learning engineer stage'
    become very similar strings.
    """
    if value is None or pd.isna(value):
        return ""

    text = str(value).lower().strip()
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[^a-z0-9àèéìòùç\s]", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def _make_dedup_key(row: pd.Series) -> str:
    """
    Create a stable key for duplicate detection.

    We use title + company + location because the same job can appear
    on multiple platforms with different URLs.
    """
    title = _normalise_text(row.get("title", ""))
    company = _normalise_text(row.get("company", ""))
    location = _normalise_text(row.get("location", ""))

    raw_key = f"{title}|{company}|{location}"

    return hashlib.md5(raw_key.encode("utf-8")).hexdigest()


def _clean_string_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Strip whitespace from all text columns."""
    cleaned = df.copy()

    for column in cleaned.columns:
        if cleaned[column].dtype == "object":
            cleaned[column] = cleaned[column].fillna("").astype(str).str.strip()

    return cleaned


def _filter_recent_jobs(df: pd.DataFrame, hours_old: int) -> pd.DataFrame:
    """
    Keep only jobs posted within the last N hours when date_posted is available.

    If date_posted is missing or cannot be parsed, we keep the row.
    This is safer because some sources do not provide reliable dates.
    """
    if "date_posted" not in df.columns or df.empty:
        return df

    cleaned = df.copy()

    parsed_dates = pd.to_datetime(
        cleaned["date_posted"],
        errors="coerce",
        utc=True,
    )

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_old)

    known_recent = parsed_dates >= cutoff
    unknown_date = parsed_dates.isna()

    return cleaned[known_recent | unknown_date].copy()


def _drop_low_quality_rows(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove rows that do not contain enough useful information.
    A useful job should have at least a title and either company or apply URL.
    """
    if df.empty:
        return df

    cleaned = df.copy()

    title_ok = cleaned.get("title", "").astype(str).str.strip() != ""

    company_ok = cleaned.get("company", "").astype(str).str.strip() != ""
    url_ok = cleaned.get("apply_url", "").astype(str).str.strip() != ""

    return cleaned[title_ok & (company_ok | url_ok)].copy()


def clean_and_deduplicate_jobs(
    jobs: pd.DataFrame,
    hours_old: int = 72,
) -> pd.DataFrame:
    """
    Clean and deduplicate job postings.

    Main responsibilities:
    1. Clean text fields
    2. Remove low-quality rows
    3. Keep recent jobs
    4. Remove duplicates
    5. Return a clean DataFrame
    """
    if jobs is None or jobs.empty:
        return pd.DataFrame()

    cleaned = jobs.copy()

    cleaned = _clean_string_columns(cleaned)
    cleaned = _drop_low_quality_rows(cleaned)
    cleaned = _filter_recent_jobs(cleaned, hours_old=hours_old)

    if cleaned.empty:
        return cleaned

    cleaned["dedup_key"] = cleaned.apply(_make_dedup_key, axis=1)

    before = len(cleaned)
    cleaned = cleaned.drop_duplicates(subset=["dedup_key"], keep="first")
    after = len(cleaned)

    cleaned = cleaned.drop(columns=["dedup_key"])

    print(f"Deduplication removed {before - after} duplicate jobs")

    cleaned = cleaned.reset_index(drop=True)

    return cleaned