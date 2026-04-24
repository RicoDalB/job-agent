from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

from agent.groq_ranker import rank_jobs_with_groq
from agent.local_ranker import rank_jobs_locally
from scraper.dedup import clean_and_deduplicate_jobs
from scraper.jobspy_fetch import fetch_jobspy_jobs
from scraper.remotive_fetch import fetch_remotive_jobs


CONFIG_PATH = Path("config.yaml")


def load_config(path: Path = CONFIG_PATH) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path, "r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    if not config:
        raise ValueError("Config file is empty")

    return config


def save_dataframe(df: pd.DataFrame, path: Path, label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    print(f"Saved {label} to: {path}")


def print_preview(df: pd.DataFrame, columns: list[str], title: str, rows: int = 10) -> None:
    if df.empty:
        print(f"\n{title}: no rows to preview")
        return

    available_columns = [column for column in columns if column in df.columns]

    if not available_columns:
        print(f"\n{title}: none of the requested preview columns exist")
        return

    print(f"\n{title}:")
    print(df[available_columns].head(rows))


def main() -> None:
    print("Job Agent started")

    config = load_config()

    output_dir = Path(config.get("paths", {}).get("output_dir", "data"))
    output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Phase 1A — Fetch jobs from JobSpy
    # ------------------------------------------------------------------
    print("\nPhase 1A — Fetching jobs with JobSpy")

    jobspy_jobs = fetch_jobspy_jobs(config)

    print(f"JobSpy jobs found: {len(jobspy_jobs)}")

    save_dataframe(
        df=jobspy_jobs,
        path=output_dir / "jobspy_raw_jobs.csv",
        label="JobSpy raw jobs",
    )

    # ------------------------------------------------------------------
    # Phase 1B — Fetch jobs from Remotive
    # ------------------------------------------------------------------
    print("\nPhase 1B — Fetching jobs with Remotive")

    remotive_jobs = fetch_remotive_jobs(config)

    print(f"Remotive jobs found: {len(remotive_jobs)}")

    save_dataframe(
        df=remotive_jobs,
        path=output_dir / "remotive_raw_jobs.csv",
        label="Remotive raw jobs",
    )

    # ------------------------------------------------------------------
    # Phase 2 — Combine all sources
    # ------------------------------------------------------------------
    print("\nPhase 2 — Combining job sources")

    all_jobs = pd.concat(
        [jobspy_jobs, remotive_jobs],
        ignore_index=True,
    )

    print(f"Combined raw jobs: {len(all_jobs)}")

    save_dataframe(
        df=all_jobs,
        path=output_dir / "combined_raw_jobs.csv",
        label="combined raw jobs",
    )

    if all_jobs.empty:
        print("\nNo jobs found from any source. Stopping pipeline.")
        return

    # ------------------------------------------------------------------
    # Phase 3 — Clean and deduplicate
    # ------------------------------------------------------------------
    print("\nPhase 3 — Cleaning and deduplicating jobs")

    hours_old = int(config.get("search", {}).get("hours_old", 72))

    clean_jobs = clean_and_deduplicate_jobs(
        jobs=all_jobs,
        hours_old=hours_old,
    )

    print(f"Clean unique jobs: {len(clean_jobs)}")

    save_dataframe(
        df=clean_jobs,
        path=output_dir / "clean_jobs.csv",
        label="clean jobs",
    )

    if clean_jobs.empty:
        print("\nNo clean jobs found after deduplication. Stopping pipeline.")
        return

    print_preview(
        df=clean_jobs,
        columns=[
            "title",
            "company",
            "location",
            "source",
            "date_posted",
            "apply_url",
        ],
        title="Clean jobs preview",
        rows=10,
    )

    # ------------------------------------------------------------------
    # Phase 4 — Rank every job locally
    # ------------------------------------------------------------------
    print("\nPhase 4 — Ranking all jobs locally")

    locally_ranked_jobs = rank_jobs_locally(
        jobs=clean_jobs,
        config=config,
    )

    print(f"Locally ranked jobs: {len(locally_ranked_jobs)}")

    save_dataframe(
        df=locally_ranked_jobs,
        path=output_dir / "ranked_jobs_local.csv",
        label="locally ranked jobs",
    )

    print_preview(
        df=locally_ranked_jobs,
        columns=[
            "local_rank",
            "local_fit_score",
            "match_bucket",
            "title",
            "company",
            "location",
            "source",
            "detected_skills",
            "seniority_signals",
            "bad_signals",
        ],
        title="Top locally ranked jobs",
        rows=20,
    )

    # ------------------------------------------------------------------
    # Phase 5 — Groq AI ranking using compact job data
    # ------------------------------------------------------------------
    print("\nPhase 5 — Ranking jobs with Groq AI")

    final_ranked_jobs = rank_jobs_with_groq(
        ranked_jobs=locally_ranked_jobs,
        config=config,
    )

    print(f"Final ranked jobs: {len(final_ranked_jobs)}")

    save_dataframe(
        df=final_ranked_jobs,
        path=output_dir / "ranked_jobs.csv",
        label="final ranked jobs",
    )

    print_preview(
        df=final_ranked_jobs,
        columns=[
            "final_rank",
            "final_score",
            "ai_fit_score",
            "local_fit_score",
            "ai_bucket",
            "has_internship_signal",
            "internship_signals",
            "title",
            "company",
            "location",
            "source",
            "ai_reason",
        ],
        title="Top final ranked jobs",
        rows=20,
    )

    print("\nPipeline completed successfully")
    print(f"Final ranked output: {output_dir / 'ranked_jobs.csv'}")


if __name__ == "__main__":
    main()