from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import gspread
import pandas as pd
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials


load_dotenv()


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


DATA_COLUMNS = [
    "run_date",
    "final_rank",
    "final_score",
    "ai_fit_score",
    "local_fit_score",
    "ai_bucket",
    "match_bucket",
    "title",
    "company",
    "location",
    "source",
    "date_posted",
    "detected_skills",
    "internship_signals",
    "has_internship_signal",
    "seniority_signals",
    "bad_signals",
    "experience_required_years",
    "ai_reason",
    "local_score_reasons",
    "apply_url",
    "description",
]


VIEW_COLUMNS = [
    "Rank",
    "Score",
    "Company",
    "Place",
    "Role",
    "Description",
    "Link",
]


def _get_env_required(name: str) -> str:
    value = os.environ.get(name)

    if not value:
        raise EnvironmentError(f"Missing required environment variable: {name}")

    return value


def _get_gspread_client() -> gspread.Client:
    """
    Authenticate with Google Sheets.

    Local development options:
    - GOOGLE_CREDENTIALS_FILE=service-account.json
    - GOOGLE_CREDENTIALS_JSON='{"type": "service_account", ...}'

    GitHub Actions option:
    - GOOGLE_CREDENTIALS_JSON from repository secrets
    """
    credentials_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    credentials_file = os.environ.get("GOOGLE_CREDENTIALS_FILE")

    if credentials_json:
        credentials_dict = json.loads(credentials_json)
        credentials = Credentials.from_service_account_info(
            credentials_dict,
            scopes=SCOPES,
        )
        return gspread.authorize(credentials)

    if credentials_file:
        credentials_path = Path(credentials_file)

        if not credentials_path.exists():
            raise FileNotFoundError(
                f"GOOGLE_CREDENTIALS_FILE does not exist: {credentials_path}"
            )

        credentials = Credentials.from_service_account_file(
            credentials_path,
            scopes=SCOPES,
        )
        return gspread.authorize(credentials)

    raise EnvironmentError(
        "Missing Google credentials. Set GOOGLE_CREDENTIALS_JSON or GOOGLE_CREDENTIALS_FILE."
    )


def _get_or_create_worksheet(
    spreadsheet: gspread.Spreadsheet,
    worksheet_name: str,
    rows: int,
    cols: int,
) -> gspread.Worksheet:
    try:
        return spreadsheet.worksheet(worksheet_name)

    except gspread.WorksheetNotFound:
        return spreadsheet.add_worksheet(
            title=worksheet_name,
            rows=max(rows, 100),
            cols=max(cols, 20),
        )


def _clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()

    cleaned = cleaned.replace([float("inf"), float("-inf")], "")
    cleaned = cleaned.fillna("")

    return cleaned


def _prepare_data_sheet_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepare the full technical data sheet.
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=DATA_COLUMNS)

    prepared = df.copy()

    if "run_date" not in prepared.columns:
        prepared.insert(
            0,
            "run_date",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

    available_columns = [
        column for column in DATA_COLUMNS if column in prepared.columns
    ]

    prepared = prepared[available_columns].copy()
    prepared = _clean_dataframe(prepared)

    return prepared


def _safe_string(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""

    return str(value).strip()


def _short_description(row: pd.Series, max_chars: int = 280) -> str:
    """
    Choose the best readable description for the dashboard.

    Priority:
    1. AI reason
    2. Local ranking reasons
    3. Job description snippet
    """
    ai_reason = _safe_string(row.get("ai_reason", ""))
    local_reasons = _safe_string(row.get("local_score_reasons", ""))
    description = _safe_string(row.get("description", ""))

    if ai_reason:
        text = ai_reason
    elif local_reasons:
        text = local_reasons
    else:
        text = description

    text = " ".join(text.split())

    if len(text) > max_chars:
        text = text[:max_chars].rstrip() + "..."

    return text


def _get_best_rank(row: pd.Series) -> Any:
    for column in ["final_rank", "local_rank"]:
        value = row.get(column, "")

        if _safe_string(value):
            return value

    return ""


def _get_best_score(row: pd.Series) -> Any:
    for column in ["final_score", "ai_fit_score", "local_fit_score"]:
        value = row.get(column, "")

        if _safe_string(value):
            return value

    return ""


def _escape_formula_text(value: str) -> str:
    """
    Escape double quotes for Google Sheets formulas.
    """
    return value.replace('"', '""')


def _hyperlink_formula(url: str) -> str:
    """
    Return the raw URL instead of a HYPERLINK formula.

    This avoids Google Sheets locale issues such as:
    - Italian formula separators
    - localized function names
    - formula parsing errors
    """
    if not url:
        return ""

    return url


def _prepare_view_sheet_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepare the clean dashboard view.

    Columns:
    Rank | Score | Company | Place | Role | Description | Link
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=VIEW_COLUMNS)

    rows = []

    for _, row in df.iterrows():
        apply_url = _safe_string(row.get("apply_url", ""))

        rows.append(
            {
                "Rank": _get_best_rank(row),
                "Score": _get_best_score(row),
                "Company": _safe_string(row.get("company", "")),
                "Place": _safe_string(row.get("location", "")),
                "Role": _safe_string(row.get("title", "")),
                "Description": _short_description(row),
                "Link": _hyperlink_formula(apply_url),
            }
        )

    prepared = pd.DataFrame(rows, columns=VIEW_COLUMNS)
    prepared = _clean_dataframe(prepared)

    return prepared


def _write_dataframe_to_worksheet(
    worksheet: gspread.Worksheet,
    df: pd.DataFrame,
    replace: bool = True,
) -> None:
    if replace:
        worksheet.clear()

    values = [df.columns.tolist()] + df.values.tolist()

    worksheet.update(
        values=values,
        range_name="A1",
        value_input_option="USER_ENTERED",
    )


def _basic_format(worksheet: gspread.Worksheet) -> None:
    worksheet.freeze(rows=1)

    worksheet.format(
        "1:1",
        {
            "textFormat": {
                "bold": True,
                "fontSize": 11,
            },
            "horizontalAlignment": "CENTER",
            "verticalAlignment": "MIDDLE",
            "backgroundColor": {
                "red": 0.88,
                "green": 0.92,
                "blue": 1.0,
            },
        },
    )

    worksheet.format(
        "A:Z",
        {
            "wrapStrategy": "WRAP",
            "verticalAlignment": "TOP",
        },
    )


def _column_width_request(
    sheet_id: int,
    start_index: int,
    end_index: int,
    pixel_size: int,
) -> dict:
    return {
        "updateDimensionProperties": {
            "range": {
                "sheetId": sheet_id,
                "dimension": "COLUMNS",
                "startIndex": start_index,
                "endIndex": end_index,
            },
            "properties": {
                "pixelSize": pixel_size,
            },
            "fields": "pixelSize",
        }
    }


def _score_color_rule(
    sheet_id: int,
    column_index: int,
    min_score: int,
    max_score: int,
    red: float,
    green: float,
    blue: float,
) -> dict:
    """
    Conditional formatting rule for the Score column.

    Uses NUMBER_BETWEEN instead of CUSTOM_FORMULA.
    This avoids locale issues with Italian/European Google Sheets.
    """
    return {
        "addConditionalFormatRule": {
            "rule": {
                "ranges": [
                    {
                        "sheetId": sheet_id,
                        "startRowIndex": 1,
                        "startColumnIndex": column_index - 1,
                        "endColumnIndex": column_index,
                    }
                ],
                "booleanRule": {
                    "condition": {
                        "type": "NUMBER_BETWEEN",
                        "values": [
                            {
                                "userEnteredValue": str(min_score),
                            },
                            {
                                "userEnteredValue": str(max_score),
                            },
                        ],
                    },
                    "format": {
                        "backgroundColor": {
                            "red": red,
                            "green": green,
                            "blue": blue,
                        }
                    },
                },
            },
            "index": 0,
        }
    }


def _format_data_sheet(
    spreadsheet: gspread.Spreadsheet,
    worksheet: gspread.Worksheet,
) -> None:
    _basic_format(worksheet)

    requests = [
        _column_width_request(worksheet.id, 0, 1, 150),
        _column_width_request(worksheet.id, 1, 7, 90),
        _column_width_request(worksheet.id, 7, 10, 220),
        _column_width_request(worksheet.id, 10, 22, 180),
    ]

    spreadsheet.batch_update({"requests": requests})


def _format_view_sheet(
    spreadsheet: gspread.Spreadsheet,
    worksheet: gspread.Worksheet,
    row_count: int,
) -> None:
    _basic_format(worksheet)

    worksheet.format(
        "A:G",
        {
            "textFormat": {
                "fontSize": 10,
            },
            "verticalAlignment": "TOP",
        },
    )

    worksheet.format(
        "A:B",
        {
            "horizontalAlignment": "CENTER",
            "textFormat": {
                "bold": True,
            },
        },
    )

    worksheet.format(
        "G:G",
        {
            "horizontalAlignment": "CENTER",
            "textFormat": {
                "bold": True,
            },
        },
    )

    width_requests = [
        _column_width_request(worksheet.id, 0, 1, 70),    # Rank
        _column_width_request(worksheet.id, 1, 2, 80),    # Score
        _column_width_request(worksheet.id, 2, 3, 180),   # Company
        _column_width_request(worksheet.id, 3, 4, 160),   # Place
        _column_width_request(worksheet.id, 4, 5, 300),   # Role
        _column_width_request(worksheet.id, 5, 6, 560),   # Description
        _column_width_request(worksheet.id, 6, 7, 110),   # Link
    ]

    spreadsheet.batch_update({"requests": width_requests})

    if row_count <= 1:
        return

    color_requests = [
        _score_color_rule(
            sheet_id=worksheet.id,
            column_index=2,
            min_score=75,
            max_score=100,
            red=0.78,
            green=0.94,
            blue=0.80,
        ),
        _score_color_rule(
            sheet_id=worksheet.id,
            column_index=2,
            min_score=50,
            max_score=74,
            red=1.0,
            green=0.95,
            blue=0.75,
        ),
        _score_color_rule(
            sheet_id=worksheet.id,
            column_index=2,
            min_score=1,
            max_score=49,
            red=1.0,
            green=0.86,
            blue=0.86,
        ),
    ]

    spreadsheet.batch_update({"requests": color_requests})


def _safe_format_data_sheet(
    spreadsheet: gspread.Spreadsheet,
    worksheet: gspread.Worksheet,
) -> None:
    try:
        _format_data_sheet(
            spreadsheet=spreadsheet,
            worksheet=worksheet,
        )

    except Exception as error:
        print(f"Warning: data sheet formatting failed: {error}")


def _safe_format_view_sheet(
    spreadsheet: gspread.Spreadsheet,
    worksheet: gspread.Worksheet,
    row_count: int,
) -> None:
    try:
        _format_view_sheet(
            spreadsheet=spreadsheet,
            worksheet=worksheet,
            row_count=row_count,
        )

    except Exception as error:
        print(f"Warning: view sheet formatting failed: {error}")


def write_ranked_jobs_to_sheet(
    ranked_jobs: pd.DataFrame,
    config: dict[str, Any],
    replace: bool = True,
) -> None:
    """
    Write ranked jobs to two worksheets:

    1. Jobs_Data
       Full technical output with all useful columns.

    2. Jobs_View
       Clean dashboard with:
       Rank | Score | Company | Place | Role | Description | Link
    """
    sheet_id = _get_env_required("GOOGLE_SHEET_ID")

    sheets_config = config.get("sheets", {})

    data_worksheet_name = sheets_config.get(
        "worksheet_name",
        "Jobs_Data",
    )

    view_worksheet_name = sheets_config.get(
        "view_worksheet_name",
        "Jobs_View",
    )

    data_df = _prepare_data_sheet_dataframe(ranked_jobs)
    view_df = _prepare_view_sheet_dataframe(ranked_jobs)

    client = _get_gspread_client()
    spreadsheet = client.open_by_key(sheet_id)

    data_worksheet = _get_or_create_worksheet(
        spreadsheet=spreadsheet,
        worksheet_name=data_worksheet_name,
        rows=len(data_df) + 1,
        cols=len(data_df.columns),
    )

    view_worksheet = _get_or_create_worksheet(
        spreadsheet=spreadsheet,
        worksheet_name=view_worksheet_name,
        rows=len(view_df) + 1,
        cols=len(view_df.columns),
    )

    _write_dataframe_to_worksheet(
        worksheet=data_worksheet,
        df=data_df,
        replace=replace,
    )

    _write_dataframe_to_worksheet(
        worksheet=view_worksheet,
        df=view_df,
        replace=replace,
    )

    _safe_format_data_sheet(
        spreadsheet=spreadsheet,
        worksheet=data_worksheet,
    )

    _safe_format_view_sheet(
        spreadsheet=spreadsheet,
        worksheet=view_worksheet,
        row_count=len(view_df) + 1,
    )

    print(
        "Google Sheet updated successfully | "
        f"data='{data_worksheet_name}' rows={len(data_df)} | "
        f"view='{view_worksheet_name}' rows={len(view_df)}"
    )