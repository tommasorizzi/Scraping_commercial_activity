"""
Website Existence Detector.

For each business from the scraping step this script:
1. Checks if a website URL was already provided by Google Maps.
2. Validates the URL with an HTTP HEAD request.
3. If no URL exists, performs a Google search fallback via SerpAPI
   to look for an official website.
4. Classifies each business as "has_website" or "no_website".

Results are saved to `.tmp/enriched_businesses.json`.

Usage (standalone):
    python execution/detect_website.py

Usage (from pipeline):
    from execution.detect_website import main as detect
    enriched = detect(businesses)
"""

import json
import os
import re
import httpx
from serpapi import GoogleSearch

from execution.utils.config import Config
from execution.utils.logger import setup_logger
from execution.utils.rate_limiter import RateLimiter

logger = setup_logger("detect_website")

# Domains to ignore when searching for business websites
_IGNORED_DOMAINS = {
    "facebook.com", "instagram.com", "twitter.com", "x.com",
    "linkedin.com", "youtube.com", "tiktok.com", "yelp.com",
    "tripadvisor.com", "google.com", "maps.google.com",
    "hitta.se", "eniro.se", "allabolag.se", "ratsit.se",
}


# ---------------------------------------------------------------------------
# URL validation
# ---------------------------------------------------------------------------

def validate_url(url: str, timeout: float = 10.0) -> bool:
    """Return True if *url* responds with a non-error status code."""
    if not url:
        return False
    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=timeout,
            verify=False,          # some small-biz sites have bad certs
        ) as client:
            resp = client.head(url)
            return resp.status_code < 400
    except Exception:
        # Try GET as fallback — some servers reject HEAD
        try:
            with httpx.Client(
                follow_redirects=True,
                timeout=timeout,
                verify=False,
            ) as client:
                resp = client.get(url, headers={"Range": "bytes=0-0"})
                return resp.status_code < 400
        except Exception:
            return False


# ---------------------------------------------------------------------------
# Google Search fallback
# ---------------------------------------------------------------------------

def search_for_website(
    business_name: str,
    city: str,
    api_key: str,
    rate_limiter: RateLimiter,
) -> str | None:
    """Use SerpAPI Google Search to find a business website.

    Returns the first plausible URL or None.
    """
    query = f"{business_name} {city} official website"
    params = {
        "engine": "google",
        "q": query,
        "num": 5,
        "api_key": api_key,
    }

    logger.debug("Fallback search: '%s'", query)

    try:
        result = rate_limiter.execute(
            lambda p=params: GoogleSearch(p).get_dict()
        )
    except Exception as exc:
        logger.warning("Fallback search failed for '%s': %s", business_name, exc)
        return None

    for entry in result.get("organic_results", []):
        link = entry.get("link", "")
        domain = _extract_domain(link)
        if domain and domain not in _IGNORED_DOMAINS:
            if validate_url(link):
                logger.info("  ↳ Found website via search: %s", link)
                return link

    return None


def _extract_domain(url: str) -> str | None:
    """Return the bare domain from a URL (e.g. 'example.com')."""
    match = re.search(r"https?://(?:www\.)?([^/]+)", url)
    return match.group(1).lower() if match else None


# ---------------------------------------------------------------------------
# Main enrichment loop
# ---------------------------------------------------------------------------

def enrich(businesses: list[dict], api_key: str) -> list[dict]:
    """Add ``website_status`` to each business dict.

    Possible statuses:
        - ``"has_website"``  — valid website URL confirmed
        - ``"no_website"``   — no website found anywhere
    """
    rate_limiter = RateLimiter(
        delay_seconds=Config.REQUEST_DELAY_SECONDS,
        max_retries=Config.MAX_RETRIES,
    )
    total = len(businesses)

    for idx, biz in enumerate(businesses, 1):
        name = biz["name"]
        logger.info("[%d/%d] Checking website for: %s", idx, total, name)

        url = biz.get("website", "").strip()

        # Case A — URL present in Google Maps data
        if url:
            if validate_url(url):
                biz["website_status"] = "has_website"
                logger.info("  ✓ Website valid: %s", url)
                continue
            else:
                logger.warning("  ✗ Listed URL unreachable: %s — trying fallback", url)
                biz["website"] = ""  # clear invalid URL

        # Case B — no URL; try Google search fallback
        found_url = search_for_website(name, biz.get("city", ""), api_key, rate_limiter)
        if found_url:
            biz["website"] = found_url
            biz["website_status"] = "has_website"
        else:
            biz["website_status"] = "no_website"
            logger.info("  ✗ No website found for %s", name)

    return businesses


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def _save(data: list[dict], path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    logger.info("Saved %d enriched businesses → %s", len(data), path)


def _load(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(
    businesses: list[dict] | None = None,
    force: bool = False,
) -> list[dict]:
    """Detect website presence for each business.

    If *businesses* is ``None``, reads from
    ``.tmp/raw_businesses.json``.  Results are cached in
    ``.tmp/enriched_businesses.json``.
    """
    Config.ensure_directories()

    output_path = os.path.join(Config.TMP_DIR, "enriched_businesses.json")

    # Checkpoint
    if os.path.exists(output_path) and not force:
        data = _load(output_path)
        logger.info("Loaded %d cached enriched businesses", len(data))
        return data

    if businesses is None:
        raw_path = os.path.join(Config.TMP_DIR, "raw_businesses.json")
        if not os.path.exists(raw_path):
            raise FileNotFoundError(
                f"{raw_path} not found. Run scrape_google_maps first."
            )
        businesses = _load(raw_path)

    if not Config.SERPAPI_KEY:
        raise ValueError("SERPAPI_KEY is required for fallback website search")

    enriched = enrich(businesses, Config.SERPAPI_KEY)
    _save(enriched, output_path)

    no_site = sum(1 for b in enriched if b.get("website_status") == "no_website")
    has_site = sum(1 for b in enriched if b.get("website_status") == "has_website")
    logger.info("Detection complete — %d with website, %d without", has_site, no_site)

    return enriched


if __name__ == "__main__":
    main()
