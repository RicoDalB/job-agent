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


def _get_groq_client() -> Groq:
    api_key = os.environ.get("GROQ_API_KEY")

    if not api_key:
        raise EnvironmentError(
            "GROQ_API_KEY not found. Add it to your environment or .env file."
        )

    return Groq(api_key=api_key)


def _extract_json(raw_text: str) -> dict:
    if not raw_text:
        raise ValueError("Empty Groq response")

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", raw_text, flags=re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in response: {raw_text}")

    return json.loads(match.group(0))


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _truncate(value: Any, max_chars: int) -> str:
    if value is None or pd.isna(value):
        return ""

    text = str(value).strip()

    if len(text) <= max_chars:
        return text

    return text[:max_chars] + "..."


def _build_candidate_profile(config: dict) -> str:
    profile = config.get("profile", {})
    preferences = config.get("preferences", {})
    search = config.get("search", {})

    return f"""
Candidate:
- Level: {profile.get("current_level", "")}
- Target seniority: {profile.get("target_seniority", [])}
- Target roles: {search.get("roles", [])}
- Target locations: {search.get("locations", [])}
- Must-have skills: {preferences.get("must_have_skills", [])}
- Preferred stack: {preferences.get("preferred_stack", [])}
- Nice to have: {preferences.get("nice_to_have", [])}
- Exclusions / penalize: {preferences.get("exclusions", [])}

Main goal:
Find internship, stage, tirocinio, junior, graduate, or entry-level roles in AI, ML, Data Engineering, Software Engineering, or Python development.
""".strip()


def _job_to_compact_dict(row: pd.Series, max_description_chars: int) -> dict:
    """
    Convert one ranked job into a compact object for Groq.

    Important:
    We do not send the full job description.
    """
    return {
        "row_id": int(row["ai_row_id"]),
        "local_rank": _safe_int(row.get("local_rank", 0)),
        "local_fit_score": _safe_int(row.get("local_fit_score", 0)),
        "title": str(row.get("title", "") or ""),
        "company": str(row.get("company", "") or ""),
        "location": str(row.get("location", "") or ""),
        "source": str(row.get("source", "") or ""),
        "job_type": str(row.get("job_type", "") or ""),
        "detected_skills": str(row.get("detected_skills", "") or ""),
        "seniority_signals": str(row.get("seniority_signals", "") or ""),
        "bad_signals": str(row.get("bad_signals", "") or ""),
        "experience_required_years": str(row.get("experience_required_years", "") or ""),
        "local_score_reasons": _truncate(
            row.get("local_score_reasons", ""),
            max_chars=400,
        ),
        "description_snippet": _truncate(
            row.get("description", ""),
            max_chars=max_description_chars,
        ),
    }


def _build_batch_prompt(
    jobs_batch: list[dict],
    config: dict,
) -> str:
    candidate_profile = _build_candidate_profile(config)

    return f"""
You are an AI job ranking assistant.

You will receive a list of jobs already ranked locally by a deterministic scoring engine.
Your task is to provide an AI fit score for EACH job.

Important:
- HARD REQUIREMENT: If a job does not explicitly mention internship, intern, stage, tirocinio, stagista, curriculare, or extracurriculare, its ai_fit_score must be 30 or lower.
- Junior, graduate, and entry-level are useful signals, but they are NOT enough unless the job also mentions internship/stage/tirocinio/intern.
- Rank every job independently.
- Be strict.
- Prefer internship, stage, tirocinio, graduate, junior, entry-level roles.
- Penalize senior, lead, staff, principal, manager, head/director roles.
- Penalize jobs requiring 3+ years of experience.
- Penalize jobs unrelated to AI, ML, Data Engineering, Software Engineering, Python, or Data Science.
- Use the local score as a useful signal, but correct it if it seems wrong.
- Do not ask for more information.
- Return JSON only.

Candidate profile:
{candidate_profile}

Jobs:
{json.dumps(jobs_batch, ensure_ascii=False, indent=2)}

Return ONLY valid JSON in this exact format:
{{
  "jobs": [
    {{
      "row_id": 1,
      "ai_fit_score": 0,
      "ai_bucket": "strong | medium | weak | poor",
      "ai_reason": "short reason, max 18 words"
    }}
  ]
}}
""".strip()


def _score_batch_with_groq(
    jobs_batch: list[dict],
    config: dict,
    client: Groq,
) -> list[dict]:
    ai_config = config.get("ai_ranking", {})

    model = ai_config.get("model", DEFAULT_MODEL)
    max_output_tokens = int(ai_config.get("max_output_tokens", 1200))

    prompt = _build_batch_prompt(
        jobs_batch=jobs_batch,
        config=config,
    )

    completion = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a strict AI job ranking assistant. "
                    "You always return valid JSON only."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0.0,
        max_tokens=max_output_tokens,
        response_format={"type": "json_object"},
    )

    raw_output = completion.choices[0].message.content
    parsed = _extract_json(raw_output)

    jobs = parsed.get("jobs", [])

    if not isinstance(jobs, list):
        raise ValueError(f"Expected 'jobs' to be a list. Got: {parsed}")

    normalized = []

    for job in jobs:
        row_id = _safe_int(job.get("row_id"), default=-1)
        score = max(0, min(100, _safe_int(job.get("ai_fit_score"), default=0)))

        bucket = str(job.get("ai_bucket", "") or "").lower().strip()
        if bucket not in {"strong", "medium", "weak", "poor"}:
            if score >= 75:
                bucket = "strong"
            elif score >= 50:
                bucket = "medium"
            elif score >= 30:
                bucket = "weak"
            else:
                bucket = "poor"

        normalized.append(
            {
                "ai_row_id": row_id,
                "ai_fit_score": score,
                "ai_bucket": bucket,
                "ai_reason": str(job.get("ai_reason", "") or ""),
                "ai_error": "",
            }
        )

    return normalized


def rank_jobs_with_groq(ranked_jobs: pd.DataFrame, config: dict) -> pd.DataFrame:
    """
    Add Groq AI ranking to every job, using compact job data.

    This does not replace local ranking.
    It adds:
    - ai_fit_score
    - ai_bucket
    - ai_reason
    - final_score
    - final_rank

    final_score combines local + AI score.
    """
    if ranked_jobs is None or ranked_jobs.empty:
        return ranked_jobs

    ai_config = config.get("ai_ranking", {})
    enabled = bool(ai_config.get("enabled", False))

    if not enabled:
        print("Groq AI ranking disabled")
        output = ranked_jobs.copy()
        output["ai_fit_score"] = ""
        output["ai_bucket"] = ""
        output["ai_reason"] = ""
        output["ai_error"] = ""
        output["final_score"] = output["local_fit_score"]
        output["final_rank"] = output["local_rank"]
        return output

    batch_size = int(ai_config.get("batch_size", 10))
    delay_seconds = int(ai_config.get("delay_seconds", 1))
    max_description_chars = int(ai_config.get("max_description_chars", 250))

    max_jobs_to_ai_rank = ai_config.get("max_jobs_to_ai_rank")
    if max_jobs_to_ai_rank in ["null", "None", ""]:
        max_jobs_to_ai_rank = None

    jobs = ranked_jobs.copy().reset_index(drop=True)
    jobs["ai_row_id"] = range(1, len(jobs) + 1)

    if max_jobs_to_ai_rank is not None:
        jobs_for_ai = jobs.head(int(max_jobs_to_ai_rank)).copy()
        jobs_not_ranked = jobs.iloc[int(max_jobs_to_ai_rank):].copy()
    else:
        jobs_for_ai = jobs.copy()
        jobs_not_ranked = pd.DataFrame(columns=jobs.columns)

    print(f"Groq AI ranking jobs: {len(jobs_for_ai)}")

    client = _get_groq_client()

    all_ai_results = []

    compact_jobs = [
        _job_to_compact_dict(row=row, max_description_chars=max_description_chars)
        for _, row in jobs_for_ai.iterrows()
    ]

    for start in range(0, len(compact_jobs), batch_size):
        batch = compact_jobs[start:start + batch_size]
        batch_number = start // batch_size + 1

        print(
            f"Groq ranking batch {batch_number} "
            f"({len(batch)} jobs)"
        )

        try:
            batch_results = _score_batch_with_groq(
                jobs_batch=batch,
                config=config,
                client=client,
            )

            all_ai_results.extend(batch_results)

        except Exception as error:
            print(f"Groq batch failed. Error: {error}")

            for job in batch:
                all_ai_results.append(
                    {
                        "ai_row_id": job["row_id"],
                        "ai_fit_score": job["local_fit_score"],
                        "ai_bucket": "",
                        "ai_reason": "Groq failed; fallback to local score",
                        "ai_error": str(error),
                    }
                )

        time.sleep(delay_seconds)

    ai_results_df = pd.DataFrame(all_ai_results)

    merged = jobs.merge(
        ai_results_df,
        on="ai_row_id",
        how="left",
    )

    merged["ai_fit_score"] = merged["ai_fit_score"].fillna(
        merged["local_fit_score"]
    )

    merged["ai_fit_score"] = merged["ai_fit_score"].astype(int)

    # Final score: mostly AI, but local score still matters.
    # You can tune this later.
    merged["final_score"] = (
        0.65 * merged["ai_fit_score"]
        + 0.35 * merged["local_fit_score"]
    ).round().astype(int)

    merged = merged.sort_values(
        by=["final_score", "local_fit_score"],
        ascending=[False, False],
    ).reset_index(drop=True)

    merged.insert(0, "final_rank", range(1, len(merged) + 1))

    if "ai_row_id" in merged.columns:
        merged = merged.drop(columns=["ai_row_id"])

    print(f"Groq AI ranking completed for {len(jobs_for_ai)} jobs")

    return merged 