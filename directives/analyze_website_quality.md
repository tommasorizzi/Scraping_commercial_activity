# Directive: Analyse Website Quality

## Objective
Score each business website on a 0–100 scale to identify outdated or low-quality sites as leads for redesign services.

## Script
`execution/analyze_website_quality.py`

## Inputs
| Parameter | Source |
|---|---|
| Business list | `.tmp/enriched_businesses.json` (or in-memory) |
| `PAGESPEED_API_KEY` | `.env` (optional — API works without key but is more rate-limited) |

## Output
- `.tmp/scored_businesses.json` — data enriched with `quality_score`, `quality_dimensions`, `quality_issues`

## Scoring Methodology

**Composite score: 0–100**, weighted across 7 dimensions:

| Dimension | Weight | Method |
|---|---|---|
| Mobile Responsiveness | 20% | Playwright viewport emulation (375px vs 1280px) |
| Performance | 15% | Google PageSpeed Insights API (mobile) |
| SSL / HTTPS | 10% | URL scheme check |
| SEO Basics | 15% | PageSpeed SEO audit + HTML meta checks |
| Accessibility | 10% | PageSpeed Accessibility audit |
| Modern Design Signals | 15% | Playwright heuristics (fonts, layout, deprecated tags) |
| Functional Checks | 15% | Sitemap, favicon, broken internal links |

### Classification
- **Score ≥ 50**: Good website → SKIP (not a lead)
- **Score 25–49**: Needs update → save as lead
- **Score < 25**: Critical → high-priority lead

## Modern Design Heuristics (Playwright)
- `<meta name="viewport">` present?
- Web fonts vs system-only fonts?
- Flexbox/Grid usage vs table layouts?
- No `<marquee>`, `<blink>`, `<center>`, Flash?
- Copyright year within last 2 years?

## Edge Cases Learned
- PageSpeed API can be slow (~10s per site). Total analysis time scales linearly.
- Some sites block headless browsers — using a realistic user-agent string.
- If PageSpeed fails, scoring degrades gracefully to Playwright-only checks.
- Sites with client-side rendering (SPA) may show empty body initially — `domcontentloaded` wait strategy handles most cases.

## Error Handling
- Per-site try/catch — one failure doesn't stop the batch.
- Failed sites get score 0 with an error note.
- All results cached in `.tmp/scored_businesses.json`.
