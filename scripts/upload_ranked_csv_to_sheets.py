from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import yaml


# Make project root importable, so this works without PYTHONPATH=.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from output.sheets_writer import write_ranked_jobs_to_sheet  # noqa: E402


CONFIG_PATH = PROJECT_ROOT / "config.yaml"
RANKED_CSV_PATH = PROJECT_ROOT / "data" / "ranked_jobs.csv"


def load_config(path: Path = CONFIG_PATH) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path, "r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    if not config:
        raise ValueError("Config file is empty")

    return config


def main() -> None:
    if not RANKED_CSV_PATH.exists():
        raise FileNotFoundError(
            f"Ranked CSV not found: {RANKED_CSV_PATH}. Run the pipeline once first."
        )

    config = load_config()

    ranked_jobs = pd.read_csv(RANKED_CSV_PATH)

    print(f"Loaded ranked jobs from CSV: {len(ranked_jobs)} rows")

    if "local_fit_score" in ranked_jobs.columns:
        before = len(ranked_jobs)

        ranked_jobs["local_fit_score"] = pd.to_numeric(
            ranked_jobs["local_fit_score"],
            errors="coerce",
        ).fillna(0)

        ranked_jobs = ranked_jobs[ranked_jobs["local_fit_score"] > 0].copy()

        after = len(ranked_jobs)

        print(f"Removed {before - after} jobs with local_fit_score = 0")

    if ranked_jobs.empty:
        print("No jobs left after filtering. Nothing to upload.")
        return

    write_ranked_jobs_to_sheet(
        ranked_jobs=ranked_jobs,
        config=config,
        replace=True,
    )


if __name__ == "__main__":
    main()