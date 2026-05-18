# Directive: Detect Website Presence

## Objective
Determine whether each scraped business has a valid website. Businesses without a website are classified as leads.

## Script
`execution/detect_website.py`

## Inputs
| Parameter | Source |
|---|---|
| Business list | `.tmp/raw_businesses.json` (or passed in-memory from pipeline) |
| `SERPAPI_KEY` | `.env` — needed for Google search fallback |

## Output
- `.tmp/enriched_businesses.json` — same data with added `website_status` field

## Logic
1. **If `website` field is non-empty**: validate with HTTP HEAD request.
   - If response is < 400 → `website_status = "has_website"`.
   - If unreachable → clear the URL, proceed to fallback.

2. **If no website URL**: perform a Google search via SerpAPI.
   - Query: `"{business name} {city} official website"`.
   - Ignore social media and directory domains (Facebook, Instagram, Hitta.se, Eniro.se, etc.).
   - Validate the first plausible result with HEAD request.
   - If valid → set `website` and `website_status = "has_website"`.
   - If nothing found → `website_status = "no_website"`.

## Edge Cases Learned
- Some small business sites reject HEAD requests — script falls back to a ranged GET.
- SSL certificate issues are common; requests use `verify=False`.
- Each fallback Google search costs 1 SerpAPI credit. Budget accordingly.

## Error Handling
- Timeouts default to 10 seconds per URL.
- Rate-limited with 2-second delays.
- Results cached in `.tmp/enriched_businesses.json`.
