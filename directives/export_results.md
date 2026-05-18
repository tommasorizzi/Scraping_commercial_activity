# Directive: Export Results

## Objective
Export the final lead data into structured spreadsheets with two tabs.

## Script
`execution/export_spreadsheet.py`

## Inputs
| Parameter | Source |
|---|---|
| Business list | `.tmp/scored_businesses.json` or `.tmp/enriched_businesses.json` |
| `credentials.json` | Project root — Google OAuth client credentials |
| `token.json` | Project root — auto-generated after first OAuth consent |

## Outputs

### Primary: Google Sheets
- New spreadsheet created per run
- Title: `Leads — {sector} in {location} — {timestamp}`
- URL logged to console and log file

### Fallback: XLSX
- `output/leads_YYYY-MM-DD_HHMM.xlsx`
- Always saved as a backup, even when Sheets export succeeds

## Sheet Structure

### Sheet 1 — "Businesses Without Website"
| Column | Description |
|---|---|
| Business Name | From Google Maps |
| Sector | Search sector |
| Address | Full address |
| City | Extracted city |
| Phone | Phone number |
| Google Maps URL | Direct link |
| Reviews | Review count |
| Rating | Star rating |
| Notes | Manual notes column |

### Sheet 2 — "Websites To Be Updated"
| Column | Description |
|---|---|
| Business Name | From Google Maps |
| Website URL | Business website |
| Google Maps URL | Direct link |
| Address | Full address |
| Phone | Phone number |
| Rating | Star rating |
| Website Quality Score | 0–100 composite score |
| Issues Detected | Semicolon-separated list |
| Notes | Manual notes column |

## Google Sheets OAuth Setup
1. Go to [Google Cloud Console](https://console.cloud.google.com/).
2. Create a project (or use an existing one).
3. Enable the **Google Sheets API**.
4. Go to **Credentials** → **Create Credentials** → **OAuth 2.0 Client ID**.
5. Application type: **Desktop app**.
6. Download the JSON → save as `credentials.json` in the project root.
7. On first run, the script opens a browser for consent and saves `token.json`.

## Edge Cases Learned
- Token auto-refreshes as long as `token.json` has a valid refresh token.
- If `credentials.json` is missing, exports to XLSX only (no error, just a warning).
- Sheet formatting (header colors, frozen rows) is applied via batchUpdate.
