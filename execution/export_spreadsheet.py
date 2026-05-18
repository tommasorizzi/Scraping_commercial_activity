"""
Spreadsheet Exporter — Google Sheets (primary) with XLSX fallback.

Generates two sheets/tabs:
  1. "Businesses Without Website"
  2. "Websites To Be Updated"

Google Sheets is the primary target.  If credentials are not available
the script falls back to a local .xlsx file in ``output/``.

Google Sheets OAuth setup:
  1. Create a project in Google Cloud Console.
  2. Enable the Google Sheets API.
  3. Create OAuth 2.0 credentials (Desktop application).
  4. Download the JSON and save it as ``credentials.json`` in the project root.
  5. On first run the script opens a browser for consent and saves ``token.json``.

Usage (standalone):
    python execution/export_spreadsheet.py

Usage (from pipeline):
    from execution.export_spreadsheet import main as export_results
    export_results(businesses)
"""

import json
import os
from datetime import datetime

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

from execution.utils.config import Config
from execution.utils.logger import setup_logger

logger = setup_logger("export_spreadsheet")

# Google API imports — optional; only needed for Sheets export
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    _GOOGLE_AVAILABLE = True
except ImportError:
    _GOOGLE_AVAILABLE = False
    logger.warning("Google API libraries not installed — Sheets export disabled")

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


# ===================================================================
# Data preparation
# ===================================================================

def _split_businesses(businesses: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split businesses into two lists: no-website and needs-update."""
    no_website: list[dict] = []
    needs_update: list[dict] = []

    threshold = Config.QUALITY_THRESHOLD

    for biz in businesses:
        status = biz.get("website_status", "")

        if status == "no_website":
            no_website.append(biz)
        elif status == "has_website":
            score = biz.get("quality_score")
            # Include if score is below threshold OR if not yet scored
            if score is not None and score < threshold:
                needs_update.append(biz)
            elif score is None:
                # Not yet analysed — include with a note
                needs_update.append(biz)

    return no_website, needs_update


def _no_website_row(biz: dict) -> list:
    """Format a single row for the 'No Website' sheet."""
    return [
        biz.get("name", ""),
        biz.get("sector", ""),
        biz.get("address", ""),
        biz.get("city", ""),
        biz.get("phone", ""),
        biz.get("google_maps_url", ""),
        biz.get("reviews", 0),
        biz.get("rating", ""),
        "",  # Notes
    ]


def _needs_update_row(biz: dict) -> list:
    """Format a single row for the 'Needs Update' sheet."""
    issues = biz.get("quality_issues", [])
    return [
        biz.get("name", ""),
        biz.get("website", ""),
        biz.get("google_maps_url", ""),
        biz.get("address", ""),
        biz.get("phone", ""),
        biz.get("rating", ""),
        biz.get("quality_score", "N/A"),
        "; ".join(issues) if issues else "",
        "",  # Notes
    ]


NO_WEBSITE_HEADERS = [
    "Business Name", "Sector", "Address", "City",
    "Phone", "Google Maps URL", "Reviews", "Rating", "Notes",
]

NEEDS_UPDATE_HEADERS = [
    "Business Name", "Website URL", "Google Maps URL", "Address",
    "Phone", "Rating", "Website Quality Score", "Issues Detected", "Notes",
]


# ===================================================================
# XLSX export (fallback)
# ===================================================================

def export_xlsx(
    no_website: list[dict],
    needs_update: list[dict],
) -> str:
    """Write both sheets to a local .xlsx file and return the path."""
    Config.ensure_directories()
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    path = os.path.join(Config.OUTPUT_DIR, f"leads_{stamp}.xlsx")

    wb = openpyxl.Workbook()

    # ---- styling ----
    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill("solid", fgColor="2F5496")
    header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )

    def _write_sheet(ws, headers, rows):
        # Headers
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_align
            cell.border = thin_border
        # Data
        for r_idx, row in enumerate(rows, 2):
            for c_idx, value in enumerate(row, 1):
                cell = ws.cell(row=r_idx, column=c_idx, value=value)
                cell.border = thin_border
                cell.alignment = Alignment(wrap_text=True)
        # Auto-width
        for col in ws.columns:
            max_len = max(
                (len(str(cell.value or "")) for cell in col), default=10,
            )
            ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 50)

    # Sheet 1 — No Website
    ws1 = wb.active
    ws1.title = "Businesses Without Website"
    rows1 = [_no_website_row(b) for b in no_website]
    _write_sheet(ws1, NO_WEBSITE_HEADERS, rows1)

    # Sheet 2 — Needs Update
    ws2 = wb.create_sheet("Websites To Be Updated")
    rows2 = [_needs_update_row(b) for b in needs_update]
    _write_sheet(ws2, NEEDS_UPDATE_HEADERS, rows2)

    wb.save(path)
    logger.info("XLSX saved → %s", path)
    return path


# ===================================================================
# Google Sheets export (primary)
# ===================================================================

def _get_sheets_service():
    """Authenticate and return a Google Sheets API service object."""
    if not _GOOGLE_AVAILABLE:
        return None

    creds = None

    if os.path.exists(Config.TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(Config.TOKEN_PATH, _SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(Config.CREDENTIALS_PATH):
                logger.warning(
                    "credentials.json not found at %s — "
                    "falling back to XLSX export",
                    Config.CREDENTIALS_PATH,
                )
                return None
            flow = InstalledAppFlow.from_client_secrets_file(
                Config.CREDENTIALS_PATH, _SCOPES,
            )
            creds = flow.run_local_server(port=0)

        with open(Config.TOKEN_PATH, "w") as token_file:
            token_file.write(creds.to_json())
        logger.info("Google OAuth token saved → %s", Config.TOKEN_PATH)

    return build("sheets", "v4", credentials=creds)


def export_google_sheets(
    no_website: list[dict],
    needs_update: list[dict],
    sector: str = "",
    location: str = "",
) -> str | None:
    """Create a Google Sheets spreadsheet with both tabs.

    Returns the spreadsheet URL or None on failure.
    """
    service = _get_sheets_service()
    if service is None:
        return None

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    title = f"Leads — {sector} in {location} — {stamp}"

    try:
        # Create spreadsheet with two sheets
        spreadsheet = (
            service.spreadsheets()
            .create(
                body={
                    "properties": {"title": title},
                    "sheets": [
                        {"properties": {"title": "Businesses Without Website"}},
                        {"properties": {"title": "Websites To Be Updated"}},
                    ],
                }
            )
            .execute()
        )
        spreadsheet_id = spreadsheet["spreadsheetId"]
        url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
        logger.info("Created Google Sheet: %s", url)

        # --- Write Sheet 1 ---
        rows1 = [NO_WEBSITE_HEADERS] + [_no_website_row(b) for b in no_website]
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range="'Businesses Without Website'!A1",
            valueInputOption="RAW",
            body={"values": rows1},
        ).execute()

        # --- Write Sheet 2 ---
        rows2 = [NEEDS_UPDATE_HEADERS] + [_needs_update_row(b) for b in needs_update]
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range="'Websites To Be Updated'!A1",
            valueInputOption="RAW",
            body={"values": rows2},
        ).execute()

        # --- Format headers (bold + color) ---
        sheet_ids = [
            s["properties"]["sheetId"] for s in spreadsheet["sheets"]
        ]
        requests = []
        for sid in sheet_ids:
            requests.append({
                "repeatCell": {
                    "range": {
                        "sheetId": sid,
                        "startRowIndex": 0,
                        "endRowIndex": 1,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": {
                                "red": 0.184, "green": 0.329, "blue": 0.588,
                            },
                            "textFormat": {
                                "bold": True,
                                "foregroundColor": {
                                    "red": 1, "green": 1, "blue": 1,
                                },
                            },
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat)",
                }
            })
            # Freeze header row
            requests.append({
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": sid,
                        "gridProperties": {"frozenRowCount": 1},
                    },
                    "fields": "gridProperties.frozenRowCount",
                }
            })

        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": requests},
        ).execute()

        logger.info(
            "Google Sheet populated — %d no-website, %d needs-update",
            len(no_website), len(needs_update),
        )
        return url

    except Exception as exc:
        logger.error("Google Sheets export failed: %s", exc)
        return None


# ===================================================================
# Entry point
# ===================================================================

def main(
    businesses: list[dict] | None = None,
    force: bool = False,
) -> dict:
    """Export leads to Google Sheets (primary) and XLSX (fallback).

    Returns a dict with keys ``sheets_url`` and ``xlsx_path``.
    """
    Config.ensure_directories()

    if businesses is None:
        # Try scored first, fall back to enriched
        for fname in ("scored_businesses.json", "enriched_businesses.json"):
            path = os.path.join(Config.TMP_DIR, fname)
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as fh:
                    businesses = json.load(fh)
                logger.info("Loaded %d businesses from %s", len(businesses), fname)
                break
        else:
            raise FileNotFoundError(
                "No business data found in .tmp/. "
                "Run the scraping and detection steps first."
            )

    no_website, needs_update = _split_businesses(businesses)

    logger.info(
        "Export summary: %d without website, %d with outdated website",
        len(no_website), len(needs_update),
    )

    result: dict = {"sheets_url": None, "xlsx_path": None}

    # Primary: Google Sheets
    sector = businesses[0].get("sector", "") if businesses else ""
    city = businesses[0].get("city", "") if businesses else ""
    sheets_url = export_google_sheets(no_website, needs_update, sector, city)
    result["sheets_url"] = sheets_url

    # Always also save XLSX as backup
    xlsx_path = export_xlsx(no_website, needs_update)
    result["xlsx_path"] = xlsx_path

    if sheets_url:
        logger.info("✓ Google Sheet: %s", sheets_url)
    else:
        logger.warning("Google Sheets export skipped — XLSX saved instead")

    logger.info("✓ XLSX backup: %s", xlsx_path)
    return result


if __name__ == "__main__":
    main()
