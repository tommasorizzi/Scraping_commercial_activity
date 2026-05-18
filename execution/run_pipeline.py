"""
Pipeline Orchestrator — runs all steps in sequence.

This is the main entry point for the scraping pipeline.  It executes
each step, uses checkpointing (intermediate JSON files in .tmp/),
and prints a summary at the end.

Usage:
    python execution/run_pipeline.py
    python execution/run_pipeline.py --sector "plumbers" --location "Södermalm, Stockholm"
    python execution/run_pipeline.py --force          # re-run everything
    python execution/run_pipeline.py --skip-quality   # skip Phase 3 scoring
"""

import argparse
import os
import sys
import time

# Ensure project root is importable
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from execution.utils.config import Config
from execution.utils.logger import setup_logger
from execution.scrape_google_maps import main as step_scrape
from execution.detect_website import main as step_detect
from execution.analyze_website_quality import main as step_analyze
from execution.export_spreadsheet import main as step_export

logger = setup_logger("pipeline")


def run(
    sector: str | None = None,
    location: str | None = None,
    coordinates: str | None = None,
    force: bool = False,
    skip_quality: bool = False,
) -> None:
    """Execute the full pipeline end-to-end."""

    start_time = time.time()
    sector = sector or Config.SEARCH_SECTOR
    location = location or Config.SEARCH_LOCATION

    logger.info("=" * 60)
    logger.info("PIPELINE START — %s in %s", sector, location)
    logger.info("=" * 60)

    # ------------------------------------------------------------------
    # Step 1 — Scrape Google Maps
    # ------------------------------------------------------------------
    logger.info("")
    logger.info("─── Step 1/4: Scraping Google Maps ───")
    businesses = step_scrape(
        sector=sector,
        location=location,
        coordinates=coordinates,
        force=force,
    )
    logger.info("Step 1 complete: %d businesses found", len(businesses))

    # ------------------------------------------------------------------
    # Step 2 — Detect websites
    # ------------------------------------------------------------------
    logger.info("")
    logger.info("─── Step 2/4: Detecting websites ───")
    enriched = step_detect(businesses=businesses, force=force)
    no_site = sum(1 for b in enriched if b.get("website_status") == "no_website")
    has_site = sum(1 for b in enriched if b.get("website_status") == "has_website")
    logger.info(
        "Step 2 complete: %d with website, %d without", has_site, no_site,
    )

    # ------------------------------------------------------------------
    # Step 3 — Website quality analysis (optional)
    # ------------------------------------------------------------------
    if skip_quality:
        logger.info("")
        logger.info("─── Step 3/4: Website quality analysis — SKIPPED ───")
        scored = enriched
    else:
        logger.info("")
        logger.info("─── Step 3/4: Analysing website quality ───")
        scored = step_analyze(businesses=enriched, force=force)
        leads = sum(
            1 for b in scored
            if b.get("quality_score") is not None
            and b["quality_score"] < Config.QUALITY_THRESHOLD
        )
        logger.info("Step 3 complete: %d website leads identified", leads)

    # ------------------------------------------------------------------
    # Step 4 — Export
    # ------------------------------------------------------------------
    logger.info("")
    logger.info("─── Step 4/4: Exporting results ───")
    result = step_export(businesses=scored)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    elapsed = time.time() - start_time
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    logger.info("")
    logger.info("=" * 60)
    logger.info("PIPELINE COMPLETE — %dm %ds", minutes, seconds)
    logger.info("=" * 60)
    logger.info("  Businesses scraped:    %d", len(businesses))
    logger.info("  Without website:       %d", no_site)
    logger.info("  With website:          %d", has_site)
    if not skip_quality:
        below = sum(
            1 for b in scored
            if b.get("quality_score") is not None
            and b["quality_score"] < Config.QUALITY_THRESHOLD
        )
        logger.info("  Outdated websites:     %d", below)
    if result.get("sheets_url"):
        logger.info("  Google Sheet:          %s", result["sheets_url"])
    if result.get("xlsx_path"):
        logger.info("  XLSX backup:           %s", result["xlsx_path"])
    logger.info("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Google Maps Lead Scraper — full pipeline",
    )
    parser.add_argument("--sector", default=None, help="Business sector")
    parser.add_argument("--location", default=None, help="Geographic area")
    parser.add_argument("--coordinates", default=None, help="GPS coords (@lat,lng,zoom)")
    parser.add_argument("--force", action="store_true", help="Ignore cached data")
    parser.add_argument(
        "--skip-quality", action="store_true",
        help="Skip website quality analysis (Phase 3)",
    )
    args = parser.parse_args()

    run(
        sector=args.sector,
        location=args.location,
        coordinates=args.coordinates,
        force=args.force,
        skip_quality=args.skip_quality,
    )
