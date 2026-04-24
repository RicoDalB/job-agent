from __future__ import annotations

import re
from pathlib import Path

import pdfplumber


def _clean_cv_text(text: str) -> str:
    """
    Clean extracted CV text.

    The goal is not to make it beautiful.
    The goal is to make it readable and useful for the LLM.
    """
    if not text:
        return ""

    # Replace weird whitespace
    text = text.replace("\x00", " ")
    text = re.sub(r"\s+", " ", text)

    # Remove excessive repeated punctuation
    text = re.sub(r"[-_=]{3,}", " ", text)

    return text.strip()


def extract_cv_text(cv_path: str | Path) -> str:
    """
    Extract text from a PDF CV using pdfplumber.

    Args:
        cv_path: Path to the CV PDF.

    Returns:
        Clean text extracted from the CV.
    """
    cv_path = Path(cv_path)

    if not cv_path.exists():
        raise FileNotFoundError(
            f"CV file not found: {cv_path}. "
            "Put your CV PDF in the project root or update config.yaml."
        )

    if cv_path.suffix.lower() != ".pdf":
        raise ValueError(f"CV file must be a PDF. Got: {cv_path}")

    extracted_pages = []

    with pdfplumber.open(cv_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            page_text = page.extract_text() or ""

            if page_text.strip():
                extracted_pages.append(page_text)
            else:
                print(f"Warning: no text found on CV page {page_number}")

    raw_text = "\n".join(extracted_pages)
    clean_text = _clean_cv_text(raw_text)

    if not clean_text:
        raise ValueError(
            "No readable text was extracted from the CV. "
            "Your PDF may be scanned as an image instead of containing selectable text."
        )

    return clean_text


def save_cv_text(cv_text: str, output_path: str | Path) -> None:
    """
    Save extracted CV text to a .txt file for debugging.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as file:
        file.write(cv_text)