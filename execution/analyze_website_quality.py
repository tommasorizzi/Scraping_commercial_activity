"""
Website Quality Analyzer — Hybrid Playwright + PageSpeed Insights.

Scores each website on a 0-100 scale across seven dimensions:

    Dimension              Weight   Method
    ─────────────────────  ──────   ───────────────────────────────
    Mobile Responsiveness   20%     Playwright viewport emulation
    Performance             15%     PageSpeed Insights API
    SSL / HTTPS             10%     URL scheme + cert check
    SEO Basics              15%     PageSpeed SEO + HTML checks
    Accessibility           10%     PageSpeed Accessibility audit
    Modern Design Signals   15%     Playwright heuristic checks
    Functional Checks       15%     Sitemap, favicon, broken links

Businesses scoring below QUALITY_THRESHOLD (default 50) are saved
as leads in the "Websites To Be Updated" sheet.

Usage (standalone):
    python execution/analyze_website_quality.py

Usage (from pipeline):
    from execution.analyze_website_quality import main as analyze
    scored = analyze(businesses)
"""

import json
import os
import re
import httpx
from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout

from execution.utils.config import Config
from execution.utils.logger import setup_logger
from execution.utils.rate_limiter import RateLimiter

logger = setup_logger("analyze_quality")

# Weights for composite score (must sum to 1.0)
WEIGHTS = {
    "mobile_responsiveness": 0.20,
    "performance": 0.15,
    "ssl": 0.10,
    "seo": 0.15,
    "accessibility": 0.10,
    "modern_design": 0.15,
    "functional": 0.15,
}


# ===================================================================
# 1. Mobile Responsiveness (Playwright)
# ===================================================================

def check_mobile_responsiveness(page, url: str) -> tuple[float, list[str]]:
    """Compare desktop vs mobile rendering to detect layout issues.

    Returns (score 0-100, list of issues).
    """
    issues: list[str] = []
    score = 100.0

    try:
        # --- Desktop viewport ---
        page.set_viewport_size({"width": 1280, "height": 720})
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(1000)

        desktop_width = page.evaluate("document.body.scrollWidth")

        # --- Mobile viewport ---
        page.set_viewport_size({"width": 375, "height": 667})
        page.wait_for_timeout(1000)

        mobile_width = page.evaluate("document.body.scrollWidth")

        # Horizontal scroll on mobile = not responsive
        if mobile_width > 400:
            issues.append(f"Horizontal scroll on mobile (width: {mobile_width}px)")
            score -= 40

        # Check for viewport meta tag
        viewport_meta = page.query_selector('meta[name="viewport"]')
        if not viewport_meta:
            issues.append("Missing <meta name='viewport'> tag")
            score -= 30

        # Check if there's a mobile nav toggle (hamburger menu)
        has_mobile_nav = page.evaluate("""() => {
            const els = document.querySelectorAll(
                '[class*="hamburger"], [class*="mobile-nav"], [class*="menu-toggle"], '
                + '[class*="nav-toggle"], [aria-label*="menu"], [aria-label*="Menu"], '
                + 'button[class*="menu"]'
            );
            return els.length > 0;
        }""")
        # Only penalise if the site has a desktop nav with several links
        nav_link_count = page.evaluate("""() => {
            const nav = document.querySelector('nav');
            return nav ? nav.querySelectorAll('a').length : 0;
        }""")
        if nav_link_count > 3 and not has_mobile_nav:
            issues.append("No mobile navigation toggle detected")
            score -= 15

    except (PwTimeout, Exception) as exc:
        issues.append(f"Mobile check failed: {exc}")
        score -= 50

    return max(score, 0), issues


# ===================================================================
# 2. Performance (PageSpeed Insights API)
# ===================================================================

def check_performance(url: str, api_key: str = "") -> tuple[float, list[str]]:
    """Fetch Lighthouse performance score from PageSpeed Insights API."""
    issues: list[str] = []

    params: dict = {
        "url": url,
        "category": "PERFORMANCE",
        "strategy": "MOBILE",
    }
    if api_key:
        params["key"] = api_key

    try:
        resp = httpx.get(
            "https://www.googleapis.com/pagespeedonline/v5/runPagespeed",
            params=params,
            timeout=30.0,
        )
        data = resp.json()
        perf = data.get("lighthouseResult", {}).get("categories", {}).get(
            "performance", {}
        )
        score = (perf.get("score") or 0) * 100

        if score < 50:
            issues.append(f"Poor performance score: {score:.0f}/100")

        return score, issues

    except Exception as exc:
        issues.append(f"PageSpeed API error: {exc}")
        return 0, issues


# ===================================================================
# 3. SSL / HTTPS
# ===================================================================

def check_ssl(url: str) -> tuple[float, list[str]]:
    """Check if the site uses HTTPS."""
    issues: list[str] = []
    if url.startswith("https://"):
        return 100, issues

    # Try to upgrade to HTTPS
    https_url = url.replace("http://", "https://", 1)
    try:
        resp = httpx.head(https_url, follow_redirects=True, timeout=10)
        if resp.status_code < 400:
            issues.append("Site works on HTTPS but listed as HTTP")
            return 60, issues
    except Exception:
        pass

    issues.append("No HTTPS support")
    return 0, issues


# ===================================================================
# 4. SEO Basics (PageSpeed + HTML)
# ===================================================================

def check_seo(page, url: str, api_key: str = "") -> tuple[float, list[str]]:
    """Evaluate basic on-page SEO signals."""
    issues: list[str] = []
    score = 100.0

    # --- HTML checks (Playwright) ---
    try:
        title = page.title()
        if not title or len(title) < 5:
            issues.append("Missing or very short <title> tag")
            score -= 20

        meta_desc = page.evaluate("""() => {
            const el = document.querySelector('meta[name="description"]');
            return el ? el.getAttribute('content') : null;
        }""")
        if not meta_desc:
            issues.append("Missing <meta name='description'>")
            score -= 15

        h1_count = page.evaluate("document.querySelectorAll('h1').length")
        if h1_count == 0:
            issues.append("No <h1> element found")
            score -= 10
        elif h1_count > 1:
            issues.append(f"Multiple <h1> elements ({h1_count})")
            score -= 5

        # Check images for alt text
        images_without_alt = page.evaluate("""() => {
            const imgs = document.querySelectorAll('img');
            let missing = 0;
            imgs.forEach(img => { if (!img.alt) missing++; });
            return missing;
        }""")
        if images_without_alt > 0:
            issues.append(f"{images_without_alt} images missing alt text")
            score -= min(images_without_alt * 3, 15)

    except Exception as exc:
        issues.append(f"SEO HTML check failed: {exc}")
        score -= 30

    # --- PageSpeed SEO audit (supplementary) ---
    try:
        params: dict = {"url": url, "category": "SEO", "strategy": "MOBILE"}
        if api_key:
            params["key"] = api_key
        resp = httpx.get(
            "https://www.googleapis.com/pagespeedonline/v5/runPagespeed",
            params=params,
            timeout=30.0,
        )
        data = resp.json()
        seo_score = (
            data.get("lighthouseResult", {})
            .get("categories", {})
            .get("seo", {})
            .get("score", 0)
        ) * 100
        # Blend: 60 % HTML checks + 40 % Lighthouse SEO
        score = score * 0.6 + seo_score * 0.4
    except Exception:
        pass  # degrade gracefully — use HTML checks only

    return max(score, 0), issues


# ===================================================================
# 5. Accessibility (PageSpeed)
# ===================================================================

def check_accessibility(url: str, api_key: str = "") -> tuple[float, list[str]]:
    """Fetch Lighthouse accessibility score."""
    issues: list[str] = []
    params: dict = {"url": url, "category": "ACCESSIBILITY", "strategy": "MOBILE"}
    if api_key:
        params["key"] = api_key

    try:
        resp = httpx.get(
            "https://www.googleapis.com/pagespeedonline/v5/runPagespeed",
            params=params,
            timeout=30.0,
        )
        data = resp.json()
        a11y = (
            data.get("lighthouseResult", {})
            .get("categories", {})
            .get("accessibility", {})
            .get("score", 0)
        ) * 100
        if a11y < 50:
            issues.append(f"Poor accessibility score: {a11y:.0f}/100")
        return a11y, issues

    except Exception as exc:
        issues.append(f"Accessibility check failed: {exc}")
        return 0, issues


# ===================================================================
# 6. Modern Design Signals (Playwright heuristics)
# ===================================================================

def check_modern_design(page) -> tuple[float, list[str]]:
    """Heuristic checks for outdated design patterns."""
    issues: list[str] = []
    score = 100.0

    try:
        checks = page.evaluate("""() => {
            const results = {};

            // Table-based layout (not data tables)
            const tables = document.querySelectorAll('table');
            let layoutTables = 0;
            tables.forEach(t => {
                if (!t.querySelector('th') && t.rows.length > 2) layoutTables++;
            });
            results.layoutTables = layoutTables;

            // Old HTML tags
            results.hasMarquee = document.querySelectorAll('marquee').length > 0;
            results.hasBlink = document.querySelectorAll('blink').length > 0;
            results.hasCenter = document.querySelectorAll('center').length > 0;
            results.hasFlash = document.querySelectorAll(
                'object[type*="flash"], embed[type*="flash"]'
            ).length > 0;

            // Copyright year
            const bodyText = document.body.innerText;
            const yearMatch = bodyText.match(/©\\s*(\\d{4})/);
            results.copyrightYear = yearMatch ? parseInt(yearMatch[1]) : null;

            // Web fonts usage (non-system fonts in computed style)
            const bodyFont = getComputedStyle(document.body).fontFamily.toLowerCase();
            const systemFonts = [
                'times new roman', 'times', 'serif', 'arial', 'helvetica',
                'sans-serif', 'courier', 'monospace',
            ];
            results.usesWebFonts = !systemFonts.some(f => bodyFont.startsWith(f));

            // Flexbox / Grid usage
            const allEls = document.querySelectorAll('*');
            let flexGrid = 0;
            allEls.forEach(el => {
                const d = getComputedStyle(el).display;
                if (d === 'flex' || d === 'grid' || d === 'inline-flex' || d === 'inline-grid') {
                    flexGrid++;
                }
            });
            results.flexGridCount = flexGrid;

            return results;
        }""")

        if checks.get("layoutTables", 0) > 0:
            issues.append("Table-based layout detected")
            score -= 25

        if checks.get("hasMarquee") or checks.get("hasBlink"):
            issues.append("Deprecated HTML elements (<marquee>/<blink>)")
            score -= 20

        if checks.get("hasCenter"):
            issues.append("Uses <center> tag (deprecated)")
            score -= 10

        if checks.get("hasFlash"):
            issues.append("Flash content detected")
            score -= 30

        copyright_year = checks.get("copyrightYear")
        current_year = 2026
        if copyright_year and copyright_year < current_year - 2:
            issues.append(f"Outdated copyright year: {copyright_year}")
            score -= 15

        if not checks.get("usesWebFonts"):
            issues.append("No web fonts — uses only system fonts")
            score -= 10

        if checks.get("flexGridCount", 0) < 2:
            issues.append("Minimal use of modern CSS layout (flexbox/grid)")
            score -= 15

    except Exception as exc:
        issues.append(f"Design check failed: {exc}")
        score -= 40

    return max(score, 0), issues


# ===================================================================
# 7. Functional Checks
# ===================================================================

def check_functional(page, url: str) -> tuple[float, list[str]]:
    """Check for sitemap, favicon, and sample broken links."""
    issues: list[str] = []
    score = 100.0
    base = url.rstrip("/")

    # Sitemap
    try:
        resp = httpx.head(f"{base}/sitemap.xml", follow_redirects=True, timeout=8)
        if resp.status_code >= 400:
            issues.append("No sitemap.xml found")
            score -= 25
    except Exception:
        issues.append("Could not check sitemap.xml")
        score -= 15

    # Favicon
    try:
        has_favicon = page.evaluate("""() => {
            return !!document.querySelector('link[rel*="icon"]');
        }""")
        if not has_favicon:
            # Try /favicon.ico
            resp = httpx.head(f"{base}/favicon.ico", follow_redirects=True, timeout=5)
            if resp.status_code >= 400:
                issues.append("No favicon found")
                score -= 15
    except Exception:
        pass

    # Sample broken links (check up to 10 internal links)
    try:
        links = page.evaluate("""() => {
            const anchors = document.querySelectorAll('a[href]');
            const urls = [];
            for (const a of anchors) {
                const href = a.href;
                if (href.startsWith(window.location.origin) && urls.length < 10) {
                    urls.push(href);
                }
            }
            return urls;
        }""")
        broken = 0
        for link in links[:10]:
            try:
                r = httpx.head(link, follow_redirects=True, timeout=5, verify=False)
                if r.status_code >= 400:
                    broken += 1
            except Exception:
                broken += 1

        if broken > 0:
            issues.append(f"{broken} broken internal link(s) found")
            score -= min(broken * 10, 40)

    except Exception:
        pass

    return max(score, 0), issues


# ===================================================================
# Composite scorer
# ===================================================================

def score_website(url: str, page, api_key: str = "") -> dict:
    """Run all checks and return a detailed score breakdown."""
    logger.info("  Analyzing: %s", url)

    dimensions: dict[str, dict] = {}

    # 1 — Mobile
    s, i = check_mobile_responsiveness(page, url)
    dimensions["mobile_responsiveness"] = {"score": s, "issues": i}

    # 2 — Performance
    s, i = check_performance(url, api_key)
    dimensions["performance"] = {"score": s, "issues": i}

    # 3 — SSL
    s, i = check_ssl(url)
    dimensions["ssl"] = {"score": s, "issues": i}

    # 4 — SEO
    s, i = check_seo(page, url, api_key)
    dimensions["seo"] = {"score": s, "issues": i}

    # 5 — Accessibility
    s, i = check_accessibility(url, api_key)
    dimensions["accessibility"] = {"score": s, "issues": i}

    # 6 — Modern design
    s, i = check_modern_design(page)
    dimensions["modern_design"] = {"score": s, "issues": i}

    # 7 — Functional
    s, i = check_functional(page, url)
    dimensions["functional"] = {"score": s, "issues": i}

    # Composite
    composite = sum(
        dimensions[dim]["score"] * weight
        for dim, weight in WEIGHTS.items()
    )

    all_issues = []
    for dim_data in dimensions.values():
        all_issues.extend(dim_data["issues"])

    return {
        "composite_score": round(composite, 1),
        "dimensions": {k: round(v["score"], 1) for k, v in dimensions.items()},
        "issues": all_issues,
    }


# ===================================================================
# Main loop
# ===================================================================

def main(
    businesses: list[dict] | None = None,
    force: bool = False,
) -> list[dict]:
    """Analyse website quality for all businesses that have a website.

    Reads from ``.tmp/enriched_businesses.json`` if *businesses* is
    not provided.  Results cached in ``.tmp/scored_businesses.json``.
    """
    Config.ensure_directories()

    output_path = os.path.join(Config.TMP_DIR, "scored_businesses.json")

    if os.path.exists(output_path) and not force:
        with open(output_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        logger.info("Loaded %d cached scored businesses", len(data))
        return data

    if businesses is None:
        src = os.path.join(Config.TMP_DIR, "enriched_businesses.json")
        if not os.path.exists(src):
            raise FileNotFoundError(f"{src} not found. Run detect_website first.")
        with open(src, "r", encoding="utf-8") as fh:
            businesses = json.load(fh)

    api_key = Config.PAGESPEED_API_KEY
    total = len(businesses)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            ignore_https_errors=True,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        for idx, biz in enumerate(businesses, 1):
            name = biz["name"]

            if biz.get("website_status") != "has_website" or not biz.get("website"):
                logger.info("[%d/%d] Skipping %s (no website)", idx, total, name)
                biz["quality_score"] = None
                biz["quality_issues"] = []
                continue

            logger.info("[%d/%d] Scoring: %s", idx, total, name)
            try:
                result = score_website(biz["website"], page, api_key)
                biz["quality_score"] = result["composite_score"]
                biz["quality_dimensions"] = result["dimensions"]
                biz["quality_issues"] = result["issues"]

                label = "GOOD" if result["composite_score"] >= Config.QUALITY_THRESHOLD else "LEAD"
                logger.info(
                    "  → Score: %.1f/100 [%s] — %d issue(s)",
                    result["composite_score"], label, len(result["issues"]),
                )
            except Exception as exc:
                logger.error("  ✗ Failed to score %s: %s", name, exc)
                biz["quality_score"] = 0
                biz["quality_issues"] = [f"Analysis failed: {exc}"]

        browser.close()

    # Save
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(businesses, fh, ensure_ascii=False, indent=2)
    logger.info("Saved scored businesses → %s", output_path)

    leads = sum(
        1 for b in businesses
        if b.get("quality_score") is not None
        and b["quality_score"] < Config.QUALITY_THRESHOLD
    )
    logger.info("Quality analysis complete — %d website leads identified", leads)

    return businesses


if __name__ == "__main__":
    main()
