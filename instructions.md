# AI Agent Specification — Google Maps Lead Scraper & Website Quality Analyzer

## Objective

Build an autonomous AI-powered scraping and analysis tool that:

1. Searches Google Maps for commercial activities/businesses within a specified sector.
2. Restricts the search to a configurable geographic area.
3. Collects business information from Google Maps and from the web.
4. Detects whether the business has a website.
5. Evaluates the quality of the website.
6. Stores the results into structured spreadsheets.
7. Asks for confirmation before making important architectural or design decisions.

---

# Core Mission

The system must identify businesses that either:

- DO NOT have a website
OR
- Have an outdated, low-quality, or poorly designed website

The final purpose is to generate qualified leads for potential website redesign or website creation services.

---

# Inputs

The tool must accept the following input parameters:

## 1. Business Sector (Required)

Examples:
- electricians
- plumbers
- restaurants
- dentists
- hairdressers
- cleaning companies
- law firms

The input may be:
- broad
- niche-specific
- multilingual

---

## 2. Geographic Area (Optional)

Default:
- Stockholm, Sweden

Examples:
- Stockholm
- Berlin
- Paris
- Malmö
- London
- New York
- Stockholm County
- Sweden
- specific radius around coordinates
- custom city list

The geographic scope must be configurable.

---

# Main Workflow

## Step 1 — Search Google Maps

Use Google Maps APIs whenever possible.

Search for all businesses matching the specified sector inside the target geographic area.

For each business, collect:

- Business name
- Google Maps URL
- Address
- Phone number
- Website URL (if available)
- Ratings
- Number of reviews
- Business category
- Coordinates (latitude/longitude)

The agent must paginate and continue until all accessible results are processed.

---

## Step 2 — Detect Website Presence

For each business:

### Case A — Website Exists in Google Maps

Access the website.

Proceed to website quality analysis.

---

### Case B — No Website Listed

Perform additional web searches to verify whether a website exists elsewhere online.

Possible strategies:
- Google Search
- Bing Search
- Company name + city search
- Domain detection

If a valid website is found:
- continue with website analysis

If NO website exists:
- classify as "No Website"

Save the business into the spreadsheet section:
- `Businesses Without Website`

---

# Website Quality Analysis

If a website exists, evaluate whether the website appears:

## GOOD / MODERN

Characteristics may include:
- responsive/mobile-friendly
- modern layout
- fast loading
- clear navigation
- HTTPS enabled
- updated branding
- professional design
- functional contact forms
- modern UX/UI

If the website quality is acceptable:
- SKIP
- do not save as a lead

---

## BAD / OUTDATED

Characteristics may include:
- broken layout
- not mobile friendly
- outdated visual style
- slow loading
- broken links
- missing SSL/HTTPS
- poor usability
- old typography
- cluttered interface
- obvious maintenance issues
- does not have a sitemap
- does not work on mobile
- does not have a booking system

If the website appears poor:
- classify as `Website To Be Updated`

Save:
- business name
- website URL
- Google Maps URL
- contact information
- notes/reasoning

---

# Spreadsheet Output Structure

The system must generate structured spreadsheets.

Preferred formats:
- CSV
- XLSX
- Google Sheets export support

---

# Spreadsheet Sections

## Sheet 1 — Businesses Without Website

Columns:
- Business Name
- Sector
- Address
- City
- Phone
- Google Maps URL
- Reviews
- Rating
- Notes

---

## Sheet 2 — Websites To Be Updated

Columns:
- Business Name
- Website URL
- Google Maps URL
- Address
- Phone
- Rating
- Website Quality Score
- Issues Detected
- Notes

---

# Website Quality Scoring

The agent should create an internal scoring system.

Example:
- 0–100 quality score

Possible criteria:
- mobile responsiveness
- performance
- accessibility
- modern design
- SEO basics
- SSL
- UX clarity

The scoring model should remain explainable.

The agent must explain and justify how the scoring works before implementation.

---

# Architecture Requirements

The agent must think carefully before implementation.

For every major technical decision, the agent MUST:
1. Explain the reasoning
2. Present alternatives
3. Explain pros and cons
4. Ask for approval before proceeding

Examples:
- scraping strategy
- API selection
- browser automation framework
- anti-bot handling
- data storage architecture
- concurrency model
- hosting strategy
- website scoring methodology

The agent must NOT silently decide critical architecture choices.

---

# Preferred Technologies

The agent may propose alternatives, but should initially consider:

## Data Collection
- Google Maps API
- Google Places API
- SerpAPI
- browser automation when necessary

## Browser Automation
- Playwright
- Puppeteer

## Backend
- Python
OR
- Node.js

## Scraping
- BeautifulSoup
- Playwright scraping
- Selenium only if justified

## Data Storage
- CSV
- XLSX
- SQLite
- PostgreSQL (optional)

---

# Important Constraints

## Respect Rate Limits

The tool must:
- avoid aggressive scraping
- implement retries
- implement delays
- handle CAPTCHAs gracefully

---

## Logging

The system must log:
- scraping progress
- failures
- blocked requests
- website analysis results
- skipped businesses

---

## Error Handling

The system must recover gracefully from:
- API failures
- invalid websites
- timeouts
- missing data
- anti-bot measures

---

# AI Agent Behavior Rules

The AI agent must:

- think step-by-step
- reason carefully before coding
- avoid assumptions
- explain architectural choices
- ask for confirmation on major decisions
- optimize for scalability and maintainability
- prioritize reliability over speed

---

# Development Phases

## Phase 1 — Architecture Proposal

The agent should first propose:
- system architecture
- APIs
- frameworks
- database design
- spreadsheet schema
- scraping strategy

The agent must WAIT for approval before implementation.

---

## Phase 2 — MVP Implementation

Build:
- Google Maps business extraction
- website detection
- spreadsheet export

---

## Phase 3 — Website Quality Analysis

Implement:
- heuristic website scoring
- UX detection
- mobile responsiveness checks

---

## Phase 4 — Scaling

Optional:
- multi-city support
- parallel scraping
- cloud deployment
- CRM integrations
- lead scoring

---

# Expected Final Deliverables

The final system should eventually provide:

1. Automated business discovery
2. Website existence detection
3. Website quality classification
4. Lead generation spreadsheets
5. Structured logs
6. Configurable search inputs
7. Scalable scraping architecture

---

# Important Final Instruction

The agent must NEVER make major implementation or design decisions autonomously.

Before every important decision, it must:
- explain the available options
- explain tradeoffs
- provide recommendations
- ask for explicit approval

The interaction should remain collaborative and iterative.