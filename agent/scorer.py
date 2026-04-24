from __future__ import annotations

import json
import os
import re
import time
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from groq import Groq


load_dotenv()


DEFAULT_MODEL = "llama-3.3-70b-versatile"


def _truncate_text(text: Any, max_chars: int = 3000) -> str:
    """Keep prompts predictable by truncating long job descriptions."""
    if text is None or pd.isna(text):
        return ""

    text = str(text).strip()

    if len(text) <= max_chars:
        return text

    return text[:max_chars] + "\n...[truncated]"


def _as_list(value: Any) -> list[str]:
    """Convert config value to list of strings."""
    if value is None:
        return []

    if isinstance(value, list):
        return [str(item) for item in value]

    return [str(value)]


def _extract_json(raw_text: str) -> dict:
    """
    Parse model output as JSON.

    Even with JSON instructions, LLMs can sometimes add text around JSON.
    This function tries direct parsing first, then extracts the first JSON object.
    """
    if not raw_text:
        raise ValueError("Empty LLM response")

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", raw_text, flags=re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in response: {raw_text}")

    return json.loads(match.group(0))


def _safe_int_score(value: Any) -> int:
    """Convert score to int and clamp between 0 and 100."""
    try:
        score = int(value)
    except (TypeError, ValueError):
        score = 0

    return max(0, min(100, score))


def _build_preferences_summary(config: dict) -> str:
    """Create a compact text version of the candidate preferences."""
    profile = config.get("profile", {})
    preferences = config.get("preferences", {})
    search = config.get("search", {})

    target_seniority = _as_list(profile.get("target_seniority"))
    roles = _as_list(search.get("roles"))
    locations = _as_list(search.get("locations"))

    must_have_skills = _as_list(preferences.get("must_have_skills"))
    preferred_stack = _as_list(preferences.get("preferred_stack"))
    nice_to_have = _as_list(preferences.get("nice_to_have"))
    exclusions = _as_list(preferences.get("exclusions"))

    return f"""
Candidate profile:
- Current level: {profile.get("current_level", "")}
- Target seniority: {target_seniority}
- Target roles/searches: {roles}
- Target locations: {locations}

Strongly preferred:
- Internships, stage, tirocinio, graduate, junior, entry-level roles
- Roles suitable for a Master's student in AI
- Italy, Europe, or remote-friendly roles

Must-have skills:
{must_have_skills}

Preferred stack:
{preferred_stack}

Nice-to-have:
{nice_to_have}

Exclusions / penalize strongly:
{exclusions}
""".strip()


def _build_scoring_prompt(job: dict, config: dict) -> str:
    """Build the scoring prompt for one job."""
    preferences_summary = _build_preferences_summary(config)

    title = job.get("title", "")
    company = job.get("company", "")
    location = job.get("location", "")
    source = job.get("source", "")
    job_type = job.get("job_type", "")
    description = _truncate_text(job.get("description", ""), max_chars=3000)

    return f"""
You are an AI career assistant helping a Master's student in Artificial Intelligence evaluate job opportunities.

Your task:
Score the job from 0 to 100 based on how well it matches the candidate profile.

Be strict and useful.

Scoring rules:
- 90-100: excellent internship/junior match, strong skills match, good location/remote fit.
- 75-89: strong match, worth applying.
- 50-74: partial match, maybe worth reviewing.
- 25-49: weak match, probably not worth applying.
- 0-24: irrelevant, too senior, wrong role, wrong location, or major mismatch.

Important:
- Reward Italian internship terms: "stage", "tirocinio", "stagista".
- Reward English internship terms: "internship", "intern", "graduate", "entry level", "junior".
- Penalize senior, lead, staff, principal, manager roles.
- Penalize roles requiring many years of experience.
- Penalize jobs unrelated to AI, software engineering, data, ML, or Python.
- Do not be overly generous.

Candidate preferences:
{preferences_summary}

Job:
Title: {title}
Company: {company}
Location: {location}
Source: {source}
Job type: {job_type}

Description:
{description}

Return ONLY valid JSON with this exact schema:
{{
  "fit_score": 0,
  "verdict": "one short sentence explaining the score",
  "matched_skills": ["skill 1", "skill 2"],
  "red_flags": ["red flag 1", "red flag 2"],
  "seniority_match": "good | partial | bad | unknown",
  "location_match": "good | partial | bad | unknown"
}}
""".strip()


def _get_groq_client() -> Groq:
    """Create Groq client using GROQ_API_KEY from environment."""
    api_key = os.environ.get("GROQ_API_KEY")

    if not api_key:
        raise EnvironmentError(
            "GROQ_API_KEY not found. Add it to your environment or .env file."
        )

    return Groq(api_key=api_key)


def score_single_job(job: dict, config: dict, client: Groq | None = None) -> dict:
    """
    Score one job using Groq.

    Returns a normalized dictionary that can be added to a DataFrame.
    """
    if client is None:
        client = _get_groq_client()

    ai_config = config.get("ai", {})
    model = ai_config.get("model", DEFAULT_MODEL)

    prompt = _build_scoring_prompt(job=job, config=config)

    completion = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a strict job matching assistant. "
                    "You always return valid JSON only."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0.1,
        max_tokens=500,
        response_format={"type": "json_object"},
    )

    raw_output = completion.choices[0].message.content
    parsed = _extract_json(raw_output)

    return {
        "fit_score": _safe_int_score(parsed.get("fit_score")),
        "verdict": str(parsed.get("verdict", "")),
        "matched_skills": ", ".join(_as_list(parsed.get("matched_skills"))),
        "red_flags": ", ".join(_as_list(parsed.get("red_flags"))),
        "seniority_match": str(parsed.get("seniority_match", "unknown")),
        "location_match": str(parsed.get("location_match", "unknown")),
    }


def score_jobs(jobs: pd.DataFrame, config: dict) -> pd.DataFrame:
    """
    Score a DataFrame of jobs.

    Adds:
    - fit_score
    - verdict
    - matched_skills
    - red_flags
    - seniority_match
    - location_match
    - scoring_error
    """
    if jobs is None or jobs.empty:
        return jobs

    ai_config = config.get("ai", {})
    max_jobs_to_score = ai_config.get("max_jobs_to_score")

    delay_seconds = int(ai_config.get("delay_seconds", 1))

    jobs_to_score = jobs.copy()

    if max_jobs_to_score is not None:
        max_jobs_to_score = int(max_jobs_to_score)
        jobs_to_score = jobs_to_score.head(max_jobs_to_score).copy()

    client = _get_groq_client()

    scored_rows = []

    for index, row in jobs_to_score.iterrows():
        job = row.to_dict()

        print(
            f"Scoring job {len(scored_rows) + 1}/{len(jobs_to_score)} "
            f"| {job.get('title', '')} | {job.get('company', '')}"
        )

        try:
            score_data = score_single_job(
                job=job,
                config=config,
                client=client,
            )

            score_data["scoring_error"] = ""

        except Exception as error:
            print(f"Scoring failed for row {index}. Error: {error}")

            score_data = {
                "fit_score": 0,
                "verdict": "Scoring failed",
                "matched_skills": "",
                "red_flags": "",
                "seniority_match": "unknown",
                "location_match": "unknown",
                "scoring_error": str(error),
            }

        scored_row = {
            **job,
            **score_data,
        }

        scored_rows.append(scored_row)

        time.sleep(delay_seconds)

    scored_df = pd.DataFrame(scored_rows)

    if "fit_score" in scored_df.columns:
        scored_df = scored_df.sort_values(
            by="fit_score",
            ascending=False,
        ).reset_index(drop=True)

    return scored_df