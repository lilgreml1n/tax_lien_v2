# LienHunter v2 - Claude Instructions

## MANDATORY: Adding a New County

**Before writing a single line of scraper code**, you MUST walk through `NEW_COUNTY_QUESTIONNAIRE.md`
with the user, section by section.

**Rule: Do NOT start coding until ALL 10 sections are answered.**

Getting this wrong means the scraper fails on page 2 or silently misses data.

When the user says "Let's add {County} County" or similar, respond by starting Section 1 of
the questionnaire and waiting for answers before proceeding to the next section.

---

## Architecture Overview

- FastAPI backend in Docker (port 8001), MySQL 8.0 (port 3306)
- DGX Spark at `raven@192.168.100.133` running Ollama (`llama3.1:70b`) on port 8001
- Two-phase pipeline: `scrape.sh` (save raw) → `assess.sh` (DGX, separate step)

## Key Files

| File | Purpose |
|------|---------|
| `backend/app/routers/scrapers.py` | All API endpoints |
| `backend/app/scrapers/arizona/apache.py` | Apache County scraper (reference implementation) |
| `backend/app/scrapers/base.py` | `HumanBehavior`, `CountyScraper`, `with_retry()` |
| `backend/app/assessment/engine.py` | Capital Guardian AI prompt (Gemini + DGX) |
| `backend/app/database.py` | Schema creation + migrations |
| `scrape.sh` | Phase 1: scrape only |
| `assess.sh` | Phase 2: assess only |
| `PLAN.md` | Master plan and layer roadmap |
| `TODO.md` | Prioritized task list |
| `NEW_COUNTY_QUESTIONNAIRE.md` | Mandatory intake for new counties |

## Coding Patterns

- All SQL uses SQLAlchemy `text()` with raw queries
- Background jobs use `threading.Thread` (NOT FastAPI BackgroundTasks - that was buggy)
- `RowMapping` must be converted to `dict()` before passing to threads
- Async scrapers run in `asyncio.new_event_loop()` inside threads
- All network calls must be wrapped with `with_retry()` from `base.py`
- Schema migrations use `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` (idempotent)

## Scraper Standards

- Use `HumanBehavior` delays: 2-8s per request, 10-30s between pages
- Rotate user agents (already in `HumanBehavior`)
- Page-level checkpoints (resume from last completed page)
- Per-parcel try/except with NULL fallback (silent failures must NOT drop the row)
- New scrapers go in `backend/app/scrapers/{state}/{county}.py`
- Register in `SCRAPER_REGISTRY` in `scrapers.py`
- **IMPORTANT**: Set `self.total_parcels_available` in every scraper (PDF/Excel: before limit; HTML: after loop)
- **For uniform templated building**: See `SCRAPER_BUILDING_GUIDE.md` (straightforward cases) vs escalate complex cases to Claude

## Job Safety Process

**Before firing any scrape/assess job:**
1. Check if a job is already `in_progress` for that state/county
2. Verify it's actually running by checking Docker logs (not just stuck in DB)
3. If stuck/dead → auto-mark as failed → allow restart
4. If truly running → block with error message
5. For assessments: if parcels stuck in `assessing` state, require `?resume=true` to reset

**Auto-restart:**
```bash
# Scraper: automatically detects dead job and restarts
./scrape.sh Arizona Apache

# Assessment: requires explicit ?resume=true flag
curl -X POST "http://localhost:8001/scrapers/assess/Arizona/Apache?resume=true"
```

**Critical**: Do NOT edit Python files while scrape/assess jobs are running — Docker auto-reload kills background threads.

## Database

- DB: `lienhunter`, user: `lienuser`, pass: `lienpass` (MySQL in Docker)
- Main table: `scraped_parcels`
- Assessment table: `assessments` (with `assessment_status`: unassessed/pending/assessing/assessed/failed)

## Capital Guardian AI Logic (4 Gates)

**Overview:** Hybrid deterministic + AI system. Gates 1-3 are pure Python logic (no guessing). Gate 4 uses Ollama llama3.1:70b to score remaining parcels.

### Gate 1: Kill Switches (100% Python — Deterministic)
Auto-reject if ANY match (no LLM needed):
- **Bankruptcy/IRS keywords** in owner name or legal description: "BANKRUPTCY", "INTERNAL REVENUE", "UNITED STATES GOVT", "FEDERAL TAX LIEN"
- **Improvement value < $10k** (likely a shack/teardown - not worth the effort)
- **Lot size < 2,500 sqft** (too small to resell)
- **Legal description contains** (environmental/structural red flags):
  - HOA, homeowners association (can't foreclose against HOA)
  - Easement, drainage basin, private road, landlocked, no access, ingress/egress
  - Flood zone A/AE, wetland, swamp, marsh
  - Superfund site, brownfield (environmental liability)
  - Undivided interest, percent interest, common area (fractional ownership = headache)

**If Gate 1 rejects:** Risk score = 0, Decision = DO_NOT_BID, assessment marked 'assessed' immediately (no LLM call).

### Gate 2: Liquidity Check (100% Python — Deterministic)
**Formula:** `(billed_amount + $3,000) / (assessed_value × 0.40) > 1.0`
- Tests if you have enough equity cushion after paying the lien
- The 0.40 factor = "what's the property realistically worth on quick sale"
- The $3,000 = estimated holding costs (property tax, insurance, etc. for 1 year)
- **If ratio > 1.0:** You'd be speculating on property appreciation, not buying equity → REJECTED

Example: $20k lien, $100k assessed → (20,000 + 3,000) / (100,000 × 0.40) = 23,000 / 40,000 = 0.575 ✅ PASS
Example: $50k lien, $100k assessed → (50,000 + 3,000) / (100,000 × 0.40) = 53,000 / 40,000 = 1.325 ❌ REJECT

### Gate 3: Scoring Signals (100% Python — Deterministic)
Computed flags fed to LLM (only for Gate 4 input, not rejection):
- **estate_flag:** Does owner name contain "ESTATE OF" or "HEIRS OF"? (YES = inherited property, often neglected)
- **mailing_differs:** Is owner's mailing address ≠ property address? (YES = absentee owner, less likely to redeem before sale)
- **equity_ratio:** Is (assessed_value / billed_amount) < 10x? (YES = tight equity, risky; NO = comfortable equity)

### Gate 4: LLM Scoring (Ollama llama3.1:70b — Contextual)
**Only reached if Parcel passed Gates 1-3.**

LLM receives all data (parcel details, tax history, gates 1-3 results) and scores based on this rubric:
```
START: 100 points
DEDUCTIONS:
  -20: Clearly rural, >30 miles from any city
  -15: Vacant land (no improvements)
  -10: Owner is LLC or corporation (harder to foreclose, more legal complexity)
  -10: equity_ratio is YES (tight equity < 10x, risky)
  -15: Years delinquent ≥ 5 (chronic non-payer, high redemption risk)
  -25: Prior liens count ≥ 3 (sold at tax sale multiple times = abandonment pattern)
ADDITIONS:
  +15: estate_flag is YES (inherited = often unmaintained, owner may be out-of-state)
  +10: mailing_differs is YES (absentee owner less likely to redeem)
FINAL: Cap at 100 max
```

**LLM Output:**
- `DECISION`: BID or DO_NOT_BID
- `RISK_SCORE`: 0-100
- `MAXIMUM_BID`: billed_amount × 1.1 (10% cushion)
- `PROPERTY_TYPE`: single-family / vacant land / mobile home / multi-family / commercial / agricultural / other
- `OWNERSHIP`: individual / LLC / trust / estate / corporate / unknown
- `CRITICAL_WARNING`: One-sentence risk or opportunity note

**Example Flow:**
```
Parcel R0012345, Saline County
  Billed: $18,500 | Assessed: $125,000 | Owner: John Smith (mailing: Colorado) | Delinquent: 2 yrs | Prior liens: 0 | Improvement: $42,000

  Gate 1: ✅ PASS (no keywords, improvement OK)
  Gate 2: ✅ PASS (ratio = 0.344 < 1.0)
  Gate 3: estate_flag=NO, mailing_differs=YES, equity_ratio=6.8x (YES=risky)

  Gate 4:
    Start 100
    -10 (equity_ratio YES)
    = 90
    +10 (mailing_differs YES)
    = 100 (capped)

    DECISION: BID
    RISK_SCORE: 100
    MAX_BID: $20,350
```

**Note:** The assessment is a screening tool, not gospel. Real investors should manually review top-scored parcels before actual bidding.

## Current State (as of 2026-02-21)

- Apache County scraper: working, ~9,750 parcels total, scrape in progress
- Assessment: working locally, requires DGX connection (VPN routing issue when remote)
- Coconino County: WORKING — assessor + owner extraction wired up. Class name fixed (CoconinaScraper). No GIS/lat-lon (ESRI backfill handles this). Next auction ~Feb 2027.
- Yavapai County: SHELL BUILT — auction scraping ready (same platform as Apache). Assessor STUBBED — wire up Monday 03/02/2026 when list goes live. Need: parcel ID format + working assessor URL.
- Mohave County: scraper WORKING, 8,680 parcels, scrape in progress. Backfill now supported via COUNTY_REGISTRY (no GIS/lat-lon available for Mohave).
- Next priorities: Let Mohave scrape finish → assess → backfill BID parcels, then Layer 1 → Layer 2 → Layer 4

### Mohave County: How to Run

**First-time setup (required after adding Playwright to Dockerfile):**
```bash
cd /Users/raven/Documents/CURRENT_PROJECTS/tax_lien_v2
docker compose build backend   # Rebuilds image with Playwright + openpyxl
docker compose up -d
```

**Register the Mohave scraper (one-time, after Docker is up):**
```bash
curl -X POST "http://localhost:8001/scrapers/config" \
  -H "Content-Type: application/json" \
  -d '{"state":"Arizona","county":"Mohave","scraper_name":"app.scrapers.arizona.mohave.MohaveScraper","scraper_version":"1.0"}'
```

**Run a quick test (50 parcels):**
```bash
curl -X POST "http://localhost:8001/scrapers/scrape/Arizona/Mohave?limit=50"
```

**Full scrape (all parcels):**
```bash
./scrape.sh Arizona Mohave
# or: caffeinate -i ./scrape.sh Arizona Mohave
```

**Mohave architecture notes:**
- Excel is downloaded ONCE via Playwright (Cloudflare-protected → browser required)
- All property details come from EagleWeb (no separate assessor site)
- No GIS/lat-lon — coordinates not available without a separate GIS lookup step
- Checkpoint "pages" = every 50 Excel rows (so resume works like Apache)
- Backfill API endpoint now accepts Arizona/Mohave (but backfill_bids.py is still Apache-only — needs update)

---

## County Reference: Mohave County, Arizona

**Parcel ID format:** `R0000332` — letter R + 7 digits (same pattern as Apache)

**Auction list (parcel source):**
- URL: https://resources.mohavecounty.us/file/Treasurer/TaxLienSale/TaxSaleList.xlsx
- Format: Excel (.xlsx) direct download — NOT a web page to scrape
- ⚠️ Behind Cloudflare — requires browser session to download (403 on raw curl)
- Must use Playwright or manual download + file import approach

**Treasurer (billed amounts + lien status):**
- URL: https://eagletw.mohavecounty.us/treasurer/treasurerweb/search.jsp
- EagleWeb system — same family as Apache's eagletreasurer
- Guest login available (no credentials needed)
- Search by parcel number, select "Tax Account Search"
- Look for "Lien Information" or "Delinquent Taxes" tab for lien status

**GIS / Mapping:**
- URL: https://www.mohave.gov/departments/treasurer/treasurer-gis-maps/
- GIS map accessible from this page (for coordinates/location)

**County Recorder (title/lien documents):**
- URL: https://eaglerss.mohave.gov/web/search/DOCSEARCH2954S1
- Search by Parcel Number or Legal Description
- Shows lien-related documents officially filed against the property title
- Use this to check for IRS liens, HOA liens, judgments, etc.

**Architecture difference vs Apache:**
- Apache: scrape HTML auction listing page → assessor per parcel → treasurer per parcel
- Mohave: download Excel file (all parcels at once) → treasurer per parcel for details
- The Excel gives you the parcel list upfront; assessor/treasurer hits happen after

## Pipeline Overview (3 Phases)

```
Phase 1: scrape.sh    →  Raw parcel data saved to scraped_parcels (no AI)
Phase 2: assess.sh    →  Capital Guardian AI runs on unassessed parcels
Phase 3: backfill     →  Re-hits assessor/GIS/treasurer to fill missing data on BID parcels
```

**Phase 3 is intentionally separate** — only runs on BID parcels to avoid wasting requests on rejects.

## Shell Scripts

```bash
# Scrape only (safe to run, can resume)
./scrape.sh Arizona Apache

# Assess only (requires DGX reachable)
./assess.sh Arizona Apache 50 5000

# Backfill: fill missing data on ALL parcels missing owner/value/GPS
docker exec -it tax_lien_v2-backend-1 python /app/app/backfill_bids.py

# Backfill: BID parcels only (faster, prioritized by risk score)
docker exec -it tax_lien_v2-backend-1 python /app/app/backfill_bids.py --bids-only

# Or trigger via API (no Docker exec needed):
# POST http://localhost:8001/scrapers/backfill/Arizona/Apache?bids_only=true

# Quick 10-parcel test
./quick_test.sh

# Keep Mac awake during long operations
caffeinate -i ./scrape.sh Arizona Apache
```

## Backfill Script (`backend/app/backfill_bids.py`)

Fills in data that the main scraper sometimes misses or that wasn't collected on older runs:
- `owner_name`, `owner_mailing_address`
- `latitude`, `longitude`, `full_address` (reverse geocoded via ESRI if needed)
- `assessed_total_value`, `assessed_land_value`, `assessed_improvement_value`
- `lot_size_acres`, `lot_size_sqft`, `legal_class`, `legal_description`
- `years_delinquent`, `prior_liens_count`, `total_outstanding`, `first_delinquent_year`
- Rebuilds `google_maps_url`, `street_view_url` if coordinates found

Uses `COALESCE` — never overwrites existing data with nulls. Safe to re-run anytime.

## MANDATORY: When Adding a New County Scraper

After completing the questionnaire and writing the scraper, you MUST also do ALL of the following:

1. **Register the scraper** in `SCRAPER_REGISTRY` in `scrapers.py`
2. **Update `backfill_bids.py`** — add an entry to `COUNTY_REGISTRY` at the top of the file. Specify the scraper class, login methods, fetch method, tx method (or `None` if included in fetch), and which DB fields to check for NULL. The API guard auto-updates from the registry — no other changes needed.
3. **Update the backfill API endpoint** in `scrapers.py` — the guard now reads from `COUNTY_REGISTRY` automatically. No changes needed unless the endpoint behavior changes.
4. **Update `CLAUDE.md`** — add the new county to the Current State section and note any quirks.
5. **Update `GETTING_STARTED.md`** — add any county-specific run commands or gotchas.
6. **Update `TODO.md`** — mark the county as complete, move any remaining items.

**If you skip any of these, the next Claude session will not know the backfill works differently for that county and will get it wrong.**

## DO NOT

- Do not start coding a new county scraper without completing the questionnaire
- Do not use FastAPI BackgroundTasks for long-running jobs (use threading.Thread)
- Do not ignore silent failures - always wrap per-parcel calls in try/except with NULL fallback
- Do not modify `apache.py` when adding new counties (it's the stable reference)
- Do not deploy without testing Apache scraper still works after schema changes
- Do not finish a new county without updating CLAUDE.md, GETTING_STARTED.md, and TODO.md
