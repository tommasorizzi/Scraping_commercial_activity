# Directive: Scrape Google Maps

## Objective
Search Google Maps for businesses in a given sector and geographic area, collecting structured data for each listing.

## Script
`execution/scrape_google_maps.py`

## Inputs
| Parameter | Source | Default |
|---|---|---|
| `sector` | CLI arg or `.env` `SEARCH_SECTOR` | `electricians` |
| `location` | CLI arg or `.env` `SEARCH_LOCATION` | `Kungsholmen, Stockholm, Sweden` |
| `coordinates` | CLI arg or `.env` `SEARCH_COORDINATES` | `@59.3326,18.0388,15z` |
| `SERPAPI_KEY` | `.env` | *(required)* |

## Output
- `.tmp/raw_businesses.json` — array of business objects

## Data Collected Per Business
- Business name, address, city, phone
- Website URL (if listed)
- Rating, number of reviews
- Sector, category
- GPS coordinates (lat/lng)
- Google Maps URL

## Behaviour
1. Queries SerpAPI `google_maps` engine with sector + location.
2. Paginates automatically (20 results/page, max ~120 total per query).
3. Rate-limited to stay within free tier (50 req/hour → 2s delay).
4. Caches results — if `.tmp/raw_businesses.json` exists, loads from cache. Pass `--force` to re-scrape.

## Edge Cases Learned
- Google Maps caps visible results at ~120 per query. To get more coverage, narrow the geographic area or use multiple sub-region searches.
- SerpAPI free tier: 250 searches/month, 50/hour. Each pagination page = 1 credit.

## Error Handling
- Retries with exponential backoff (3 attempts).
- Logs all failures to `logs/scraper_YYYY-MM-DD.log`.
- If all retries fail for a page, stops pagination and returns partial results.
