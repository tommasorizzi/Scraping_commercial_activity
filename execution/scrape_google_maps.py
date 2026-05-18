"""
Google Maps Business Scraper — SerpAPI integration.

Searches Google Maps for businesses matching a sector within a target
geographic area.  Handles pagination automatically and caches results
to `.tmp/raw_businesses.json` so re-runs are free.

Usage (standalone):
    python execution/scrape_google_maps.py --sector "electricians"

Usage (from pipeline):
    from execution.scrape_google_maps import main as scrape
    businesses = scrape()
"""

import json
import os
import argparse
from serpapi import GoogleSearch

from execution.utils.config import Config
from execution.utils.logger import setup_logger
from execution.utils.rate_limiter import RateLimiter

logger = setup_logger("scrape_google_maps")


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def search_google_maps(
    sector: str,
    location: str,
    coordinates: str,
    api_key: str,
) -> list[dict]:
    """Query SerpAPI's google_maps engine and paginate through all results.

    Google Maps typically returns a maximum of ~120 results per query,
    served in pages of 20.  We follow the pagination until exhausted.
    """
    all_results: list[dict] = []
    rate_limiter = RateLimiter(
        delay_seconds=Config.REQUEST_DELAY_SECONDS,
        max_retries=Config.MAX_RETRIES,
    )
    start = 0

    while True:
        params = {
            "engine": "google_maps",
            "q": f"{sector} in {location}",
            "ll": coordinates,
            "type": "search",
            "start": start,
            "api_key": api_key,
        }

        logger.info(
            "Searching Google Maps: '%s' in '%s' (offset %d)",
            sector, location, start,
        )

        try:
            result = rate_limiter.execute(
                lambda p=params: GoogleSearch(p).get_dict()
            )
        except Exception as exc:
            logger.error("Failed at offset %d: %s", start, exc)
            break

        local_results = result.get("local_results", [])
        if not local_results:
            logger.info(
                "No more results at offset %d. Total: %d", start, len(all_results),
            )
            break

        for item in local_results:
            biz = _extract(item, sector, location)
            all_results.append(biz)
            logger.info("  ✓ %s — %s", biz["name"], biz.get("website") or "no website")

        # Follow pagination if available
        if result.get("serpapi_pagination", {}).get("next"):
            start += len(local_results)
        else:
            logger.info("Last page reached. Total: %d", len(all_results))
            break

    return all_results


def _extract(item: dict, sector: str, location: str) -> dict:
    """Normalise a single SerpAPI local_result into our schema."""
    gps = item.get("gps_coordinates", {})
    city = location.split(",")[0].strip() if "," in location else location
    return {
        "name": item.get("title", "Unknown"),
        "place_id": item.get("place_id", ""),
        "address": item.get("address", ""),
        "city": city,
        "phone": item.get("phone", ""),
        "website": item.get("website", ""),
        "rating": item.get("rating"),
        "reviews": item.get("reviews", 0),
        "sector": sector,
        "category": item.get("type", sector),
        "latitude": gps.get("latitude"),
        "longitude": gps.get("longitude"),
        "google_maps_url": item.get("link", ""),
    }


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def _save(data: list[dict], path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    logger.info("Saved %d businesses → %s", len(data), path)


def _load(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(
    sector: str | None = None,
    location: str | None = None,
    coordinates: str | None = None,
    force: bool = False,
) -> list[dict]:
    """Scrape Google Maps and return the list of businesses.

    Results are cached in ``.tmp/raw_businesses.json``.  Pass
    ``force=True`` to ignore the cache and re-scrape.
    """
    Config.ensure_directories()

    sector = sector or Config.SEARCH_SECTOR
    location = location or Config.SEARCH_LOCATION
    coordinates = coordinates or Config.SEARCH_COORDINATES

    if not Config.SERPAPI_KEY:
        raise ValueError(
            "SERPAPI_KEY is not set. Add it to your .env file.\n"
            "Get a free key at https://serpapi.com/manage-api-key"
        )

    output_path = os.path.join(Config.TMP_DIR, "raw_businesses.json")

    # Checkpoint: reuse cached results unless forced
    if os.path.exists(output_path) and not force:
        data = _load(output_path)
        logger.info("Loaded %d cached businesses from %s", len(data), output_path)
        return data

    results = search_google_maps(sector, location, coordinates, Config.SERPAPI_KEY)
    _save(results, output_path)

    logger.info(
        "Scraping complete — %d businesses for '%s' in '%s'",
        len(results), sector, location,
    )
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape Google Maps for businesses")
    parser.add_argument("--sector", default=None)
    parser.add_argument("--location", default=None)
    parser.add_argument("--coordinates", default=None)
    parser.add_argument("--force", action="store_true", help="Ignore cache")
    args = parser.parse_args()
    main(args.sector, args.location, args.coordinates, args.force)
