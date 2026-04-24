from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import pandas as pd


DEFAULT_STRICT_INTERNSHIP_TERMS = [
    "stage",
    "tirocinio",
    "stagista",
    "internship",
    "intern",
    "internship program",
    "curricular internship",
    "extra-curricular internship",
    "curriculare",
    "extracurriculare",
]

DEFAULT_SOFT_ENTRY_LEVEL_TERMS = [
    "junior",
    "graduate",
    "entry level",
    "apprendistato",
    "apprenticeship",
]

DEFAULT_TARGET_ROLE_TERMS = [
    "ai",
    "artificial intelligence",
    "machine learning",
    "ml",
    "data engineer",
    "data scientist",
    "software engineer",
    "sviluppatore",
    "sviluppatore ai",
    "sviluppatore python",
    "python developer",
    "backend developer",
]

DEFAULT_BAD_SENIORITY_TERMS = [
    "senior",
    "lead",
    "staff",
    "principal",
    "manager",
    "responsabile",
    "head of",
    "director",
    "5+ years",
    "7+ years",
    "10+ years",
    "5 anni",
    "7 anni",
    "10 anni",
]


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []

    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]

    return [str(value).strip()]


def _normalise_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""

    text = str(value).lower()
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def _contains_terms(text: str, terms: list[str]) -> list[str]:
    matches = []

    for term in terms:
        term_norm = term.lower().strip()

        if not term_norm:
            continue

        if term_norm in text:
            matches.append(term)

    return sorted(set(matches), key=lambda item: item.lower())


def _extract_years_required(text: str) -> list[int]:
    """
    Extract experience requirements like:
    - 2+ years
    - 3 years
    - 2 anni
    - almeno 3 anni
    """
    patterns = [
        r"(\d{1,2})\+?\s*(?:years|year)",
        r"(\d{1,2})\+?\s*(?:anni|anno)",
    ]

    years = []

    for pattern in patterns:
        for match in re.findall(pattern, text, flags=re.IGNORECASE):
            try:
                years.append(int(match))
            except ValueError:
                continue

    return years


def _freshness_score(date_posted: Any) -> tuple[int, str]:
    """
    Give a small bonus for recent jobs.
    Missing dates are not penalized heavily because some sources do not expose dates.
    """
    if date_posted is None or pd.isna(date_posted) or str(date_posted).strip() == "":
        return 2, "unknown date"

    parsed = pd.to_datetime(date_posted, errors="coerce", utc=True)

    if pd.isna(parsed):
        return 2, "unparsed date"

    now = datetime.now(timezone.utc)
    age_hours = (now - parsed.to_pydatetime()).total_seconds() / 3600

    if age_hours <= 24:
        return 5, "posted in last 24h"

    if age_hours <= 72:
        return 3, "posted in last 72h"

    return 1, "older posting"


def _location_score(location_text: str, config: dict) -> tuple[int, list[str]]:
    search = config.get("search", {})
    configured_locations = _as_list(search.get("locations"))

    location_matches = []

    for location in configured_locations:
        location_norm = location.lower().replace(", italy", "").strip()

        if not location_norm:
            continue

        if location_norm in location_text:
            location_matches.append(location)

    remote_terms = ["remote", "remoto", "ibrido", "hybrid"]
    remote_matches = _contains_terms(location_text, remote_terms)

    if location_matches and remote_matches:
        return 15, location_matches + remote_matches

    if location_matches:
        return 12, location_matches

    if remote_matches:
        return 10, remote_matches

    if "italy" in location_text or "italia" in location_text:
        return 8, ["Italy"]

    return 2, []


def _build_compressed_summary(row: pd.Series, max_description_chars: int = 500) -> str:
    title = str(row.get("title", "") or "").strip()
    company = str(row.get("company", "") or "").strip()
    location = str(row.get("location", "") or "").strip()
    source = str(row.get("source", "") or "").strip()
    description = str(row.get("description", "") or "").strip()

    if len(description) > max_description_chars:
        description = description[:max_description_chars] + "..."

    return (
        f"Title: {title}\n"
        f"Company: {company}\n"
        f"Location: {location}\n"
        f"Source: {source}\n"
        f"Description snippet: {description}"
    )


def _score_job(row: pd.Series, config: dict) -> dict:
    preferences = config.get("preferences", {})
    local_ranking = config.get("local_ranking", {})

    must_have_skills = _as_list(preferences.get("must_have_skills"))
    preferred_stack = _as_list(preferences.get("preferred_stack"))
    nice_to_have = _as_list(preferences.get("nice_to_have"))
    exclusions = _as_list(preferences.get("exclusions"))

    strict_internship_terms = _as_list(
        local_ranking.get("strict_internship_terms", DEFAULT_STRICT_INTERNSHIP_TERMS)
    )

    soft_entry_level_terms = _as_list(
        local_ranking.get("soft_entry_level_terms", DEFAULT_SOFT_ENTRY_LEVEL_TERMS)
    )

    require_internship_signal = bool(
        local_ranking.get("require_internship_signal", True)
    )

    no_internship_max_score = int(
        local_ranking.get("no_internship_max_score", 30)
    )
    target_role_terms = _as_list(
        local_ranking.get("target_role_terms", DEFAULT_TARGET_ROLE_TERMS)
    )
    bad_seniority_terms = _as_list(
        local_ranking.get("bad_seniority_terms", DEFAULT_BAD_SENIORITY_TERMS)
    )

    title = _normalise_text(row.get("title", ""))
    company = _normalise_text(row.get("company", ""))
    location = _normalise_text(row.get("location", ""))
    description = _normalise_text(row.get("description", ""))
    job_type = _normalise_text(row.get("job_type", ""))
    source = _normalise_text(row.get("source", ""))

    title_text = f"{title} {job_type}"
    full_text = f"{title} {company} {location} {job_type} {description}"

    score = 0
    reasons = []

    # 1. Internship fit: hard requirement
    strict_internship_signals = _contains_terms(full_text, strict_internship_terms)
    title_internship_signals = _contains_terms(title_text, strict_internship_terms)

    soft_entry_level_signals = _contains_terms(full_text, soft_entry_level_terms)
    title_soft_entry_level_signals = _contains_terms(title_text, soft_entry_level_terms)

    has_internship_signal = bool(strict_internship_signals)

    if title_internship_signals:
        score += 35
        reasons.append(
            f"title internship match: {', '.join(title_internship_signals[:4])}"
        )
    elif strict_internship_signals:
        score += 25
        reasons.append(
            f"internship match: {', '.join(strict_internship_signals[:4])}"
        )
    elif title_soft_entry_level_signals:
        score += 8
        reasons.append(
            f"soft entry-level match only: {', '.join(title_soft_entry_level_signals[:4])}"
        )
    elif soft_entry_level_signals:
        score += 5
        reasons.append(
            f"soft entry-level signal only: {', '.join(soft_entry_level_signals[:4])}"
        )
    else:
        reasons.append("missing internship/stage signal")

    # 2. Role relevance
    role_matches_title = _contains_terms(title_text, target_role_terms)
    role_matches_full = _contains_terms(full_text, target_role_terms)

    if role_matches_title:
        score += min(22, 10 + 4 * len(role_matches_title))
        reasons.append(f"title role match: {', '.join(role_matches_title[:5])}")
    elif role_matches_full:
        score += min(14, 4 * len(role_matches_full))
        reasons.append(f"role match: {', '.join(role_matches_full[:5])}")

    # 3. Skills
    must_matches = _contains_terms(full_text, must_have_skills)
    preferred_matches = _contains_terms(full_text, preferred_stack)
    nice_matches = _contains_terms(full_text, nice_to_have)

    skill_score = 0
    skill_score += min(18, 6 * len(must_matches))
    skill_score += min(14, 3 * len(preferred_matches))
    skill_score += min(8, 2 * len(nice_matches))

    score += skill_score

    detected_skills = sorted(
        set(must_matches + preferred_matches + nice_matches),
        key=lambda item: item.lower(),
    )

    if detected_skills:
        reasons.append(f"skills: {', '.join(detected_skills[:8])}")

    # 4. Location
    loc_score, loc_matches = _location_score(location, config)
    score += loc_score

    if loc_matches:
        reasons.append(f"location: {', '.join(loc_matches[:4])}")
    else:
        reasons.append("weak location match")

    # 5. Freshness
    fresh_score, freshness_reason = _freshness_score(row.get("date_posted", ""))
    score += fresh_score
    reasons.append(freshness_reason)

    # 6. Source bonus
    if source == "linkedin":
        score += 2
        reasons.append("source: LinkedIn")
    elif source == "indeed":
        score += 2
        reasons.append("source: Indeed")
    elif source == "remotive":
        score += 1
        reasons.append("source: Remotive")

    # 7. Penalties
    bad_signals = _contains_terms(full_text, bad_seniority_terms + exclusions)

    if bad_signals:
        penalty = min(30, 10 + 5 * len(bad_signals))
        score -= penalty
        reasons.append(f"bad signals: {', '.join(bad_signals[:6])}")

    years_required = _extract_years_required(full_text)

    if years_required:
        max_years = max(years_required)

        if max_years >= 5:
            score -= 25
            reasons.append(f"high experience requirement: {max_years} years")
        elif max_years >= 3:
            score -= 15
            reasons.append(f"medium experience requirement: {max_years} years")
        elif max_years >= 1:
            score -= 3
            reasons.append(f"low experience requirement: {max_years} years")

    # 8. Description quality
    if len(description) < 100:
        score -= 5
        reasons.append("short/missing description")
    
    # Hard cap if internship/stage signal is required but missing.
    # This keeps all jobs in the ranking, but pushes non-internship jobs down.
    if require_internship_signal and not has_internship_signal:
        score = min(score, no_internship_max_score)
        bad_signals.append("missing internship/stage signal")
        reasons.append(f"score capped at {no_internship_max_score}: no internship/stage")

    # Clamp final score
    score = max(0, min(100, int(score)))

    if score >= 75:
        bucket = "strong"
    elif score >= 50:
        bucket = "medium"
    elif score >= 30:
        bucket = "weak"
    else:
        bucket = "poor"

    return {
        "local_fit_score": score,
        "match_bucket": bucket,
        "detected_skills": ", ".join(detected_skills),
        "has_internship_signal": has_internship_signal,
        "internship_signals": ", ".join(strict_internship_signals),
        "seniority_signals": ", ".join(strict_internship_signals + soft_entry_level_signals),
        "bad_signals": ", ".join(bad_signals),
        "experience_required_years": max(years_required) if years_required else "",
        "local_score_reasons": "; ".join(reasons),
        "compressed_job_summary": _build_compressed_summary(row),
    }


def rank_jobs_locally(jobs: pd.DataFrame, config: dict) -> pd.DataFrame:
    """
    Rank every job locally without using an LLM.

    This is the main ranking engine of the project.
    It is free, fast, and can run on hundreds/thousands of jobs.
    """
    if jobs is None or jobs.empty:
        return jobs

    local_ranking = config.get("local_ranking", {})
    enabled = bool(local_ranking.get("enabled", True))

    if not enabled:
        print("Local ranking disabled")
        return jobs

    ranked_rows = []

    for _, row in jobs.iterrows():
        score_data = _score_job(row=row, config=config)

        ranked_rows.append(
            {
                **row.to_dict(),
                **score_data,
            }
        )

    ranked_df = pd.DataFrame(ranked_rows)

    ranked_df = ranked_df.sort_values(
        by=[
            "local_fit_score",
            "date_posted",
        ],
        ascending=[False, False],
    ).reset_index(drop=True)

    ranked_df.insert(0, "local_rank", range(1, len(ranked_df) + 1))

    print(f"Locally ranked {len(ranked_df)} jobs")

    return ranked_df