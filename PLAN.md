# LienHunter v2 - Master Plan

## Vision
Automated tax lien investment platform using AI to identify high-probability
redemption opportunities within a $50k capital budget. Target: 10-20 active
liens simultaneously, 80%+ success rate, 30% capital held in reserve for
subsequent year taxes.

---

## Budget Reality Check
- Total capital: $50,000
- Reserve (30% for subsequent year taxes): $15,000
- Deployable capital: $35,000
- Max liens at once: 10-20
- Max per lien: $1,750 - $3,500 (at 10-20 liens from $35k)
- Acceptable failure rate: 20% (2 out of 10)

---

## Current Architecture

```
PHASE 1: SCRAPE                      PHASE 2: ASSESS
───────────────────────              ─────────────────────────
County Auction Site                  DGX Spark (Ollama)
  → Parcel IDs                         → Capital Guardian AI
  → Face Amount / Billed Amount        → 4 logic gates
                                        → BID / DO_NOT_BID
Treasurer Site                          → Risk score
  → Billed Amount                       → Kill switch reason

Assessor Site
  → Owner name + mailing address
  → Property address + GPS
  → Lot size, zoning, legal class
  → Assessed land/improvement/total value
  → Legal description

         ↓                                      ↓
    MySQL Database                  MySQL (assessments table)
```

### Stack
- FastAPI backend (Docker, port 8001)
- MySQL 8.0 (Docker, port 3306)
- DGX Spark at 192.168.100.133 running Ollama (llama3.1:8b)
- Two scrapers: Apache ✅  Coconino ⚠️ (partial)

---

## Reconciliation: What We Built vs The Blueprint

### What The Blueprint Got Right (Gaps We Need To Fill)

**1. Raw HTML Storage**
We parse HTML and throw it away. If our regex misses something, it's gone.
Llama can't re-read data we didn't store.
→ Need: `raw_html` column in `scraped_parcels`

**2. Permit & Code Enforcement Scraper (The Stealth Filter)**
Tax portals are 6 months out of date. A property showing as "Family Home"
may have an active Demolition Order or Unsafe Structure notice.
→ Need: Secondary scraper for Building/Code Enforcement department
→ Logic: Open demolition order OR unsafe structure notice = auto-reject
→ Trap this prevents: Buying a lien on a house the city bulldozes next week.
  Your lien becomes a lien on debris (land), which you explicitly don't want.

**3. Owner Life-Cycle as Alpha Signal**
"Estate of" owners and absentee owners are the highest-probability targets.
Our AI prompt doesn't analyze the owner data we already scrape.
→ Need: Prompt logic for:
  - Mailing address ≠ property address → flag as absentee
  - Owner name contains "Estate of" → prioritize (unmanaged estate)
  - Last sale date > 30 years ago → likely inherited/forgotten property
  - These properties have the highest probability of non-redemption

**4. Subsequent Tax Fund Modeling**
If you spend all $50k on day one, a bigger investor buys a lien OVER yours
next year (sandwich position). You lose your priority.
→ Need: `projected_annual_cost` column
→ Need: `reserve_required` = lien_amount × 30% buffer
→ Need: Portfolio view showing total deployed vs reserve remaining
→ Rule: Never deploy more than 70% of capital ($35k of $50k)

**5. Equity Buffer - The 10x Rule**
Blueprint rule: assessed_value / lien_amount < 10 → flag as "Marginal"
Why: Need room for lawyer fees, realtor fees, subsequent taxes on foreclosure.
Our current Gate 2 uses: (lien + $3k) / (assessed × 0.40) > 1.0 → reject
→ Need: Both checks. They catch different failure modes.

**6. AI Prompt Is Not Using Our Data**
We scrape owner name, mailing address, assessed values, zoning, legal
description - but the Capital Guardian prompt only receives:
parcel_id, address, billed_amount, legal_class.
We're leaving data on the table.
→ Need: Feed ALL scraped fields to the AI

### What We Built That The Blueprint Doesn't Cover

**1. Checkpoint / Resume**
Long scrapes crash. Without checkpoints, you restart from page 1.
Apache County = 195 pages. Losing progress = hours of re-work.
→ Built: Page-level checkpoints, resume from last completed page

**2. Retry Logic With Timer**
Network blips kill jobs silently. One DNS failure = entire scrape lost.
→ Built: with_retry() in base.py - retries for up to 5 minutes before failing

**3. Per-County Scraper Registry + Questionnaire**
Adding new counties ad-hoc creates inconsistent scrapers.
→ Built: Pluggable scraper registry (scraper_configs table)
→ Built: NEW_COUNTY_QUESTIONNAIRE.md - guided intake for new counties
→ Built: COUNTY_SCRAPER_SPEC.md - patterns and template

**4. Two-Phase Pipeline (Scrape Separate From Assess)**
Waiting for full scrape before assessing wastes hours.
→ Built: scrape.sh and assess.sh are fully independent
→ Can run assessment on first 200 parcels while scraping continues

**5. Budget Filter at Assessment Time**
Wasting DGX compute assessing $50k parcels you can't afford.
→ Built: max_cost parameter on assess endpoint

**6. Human-Like Scraping**
Aggressive scrapers get blocked. County sites have bot detection.
→ Built: HumanBehavior class - random delays, rotating user agents,
  page delays between paginated requests

---

## The New Combined Plan (Layers To Build)

### Layer 1: Data Completeness
**Priority: HIGH - Everything downstream depends on this**
- [ ] Add `raw_html` column to `scraped_parcels` (TEXT/LONGTEXT)
- [ ] Store full assessor page HTML per parcel during scrape
- [ ] Store full treasurer page HTML per parcel during scrape
- [ ] Pass ALL scraped fields to Capital Guardian prompt (not just 4 fields)

### Layer 2: Smarter Capital Guardian Prompt
**Priority: HIGH - This is the core investment filter**
- [ ] Add 10x equity rule: assessed_value / lien_amount < 10 → "Marginal"
- [ ] Add "Estate of" detection → priority flag
- [ ] Add absentee owner logic: mailing ≠ property address → flag
- [ ] Add last sale date > 30 years → unmanaged estate priority
- [ ] Add bankruptcy/IRS keyword scan in legal description / owner name
- [ ] Add in-state vs out-of-state owner check
- [ ] Add structure age vs value ("shack" detection)
  - improvement_value < $10k on a residential parcel = likely shack
- [ ] Update status values: NEW → AI_EVALUATING → FLAG_LIABILITY → READY_FOR_VIBE_CHECK

### Layer 3: Permit & Code Enforcement Scraper
**Priority: HIGH - Prevents the worst outcomes**
- [ ] Research building/code enforcement department URLs per county
- [ ] Add `permit_status` field to `scraped_parcels`
- [ ] Add `code_violations` field (demolition order, unsafe structure, etc.)
- [ ] New kill switch in Capital Guardian: open violations = auto-reject
- [ ] Run permit check only on parcels that pass Gate 1 (don't waste requests)

### Layer 4: Financial Modeling
**Priority: HIGH - Protects capital**
- [ ] Add `projected_annual_cost` column (estimated year 2 tax amount)
- [ ] Add `reserve_required` column (lien_amount × 0.30)
- [ ] Add `total_holding_cost` (lien + reserve + projected year 2)
- [ ] Add portfolio endpoint: total deployed, reserve used, available capital
- [ ] Enforce: never recommend BID if it would exceed 70% of $50k deployed
- [ ] Add `subsequent_tax_estimate` based on current year billed amount

### Layer 5: Vibe-Check Frontend
**Priority: MEDIUM - Human review layer**
- [ ] Simple list view: parcel, confidence score, decision, Maps link
- [ ] KEEP / TRASH buttons (updates review_status)
- [ ] Flag for manual review (FLAG_LIABILITY status)
- [ ] Show: billed amount, assessed value, equity ratio, owner type
- [ ] Google Maps link prominent on each row
- [ ] Filter by: BID only, by county, by score range, by status

### Layer 6: Move Stack to DGX
**Priority: MEDIUM - Enables 24/7 unattended operation**
- [ ] Move docker-compose to DGX Spark
- [ ] No more Mac sleep / VPN routing issues
- [ ] Scrape and assess run overnight unattended
- [ ] Access via SSH or VPN from anywhere

### Layer 7: Multi-County Expansion
**Priority: MEDIUM - More data = better opportunities**
- [ ] Fix Coconino (wire up assessor, add error handling)
- [ ] Add Maricopa County (largest AZ county)
- [ ] Add Pima County (Tucson area)
- [ ] Add Yavapai County
- [ ] Use questionnaire process for each new county

### Layer 8: Discord Notifications
**Priority: MEDIUM - Remote visibility**
- [ ] Webhook on: scrape started/completed/crashed
- [ ] Webhook on: assessment complete with BID count
- [ ] Webhook on: new BID found with parcel details + Maps link
- [ ] Daily summary: total scraped, assessed, BIDs available
- [ ] No bot needed - just a Discord webhook URL in config

---

## Data Flow (Target State)

```
Auction Site ──→ Parcel ID + Face Amount
                         │
Treasurer ───────────────┤ billed_amount
                         │
Assessor ────────────────┤ address, GPS, owner, value, zoning
                         │ + raw_html stored
                         │
Building Dept ───────────┤ permit_status, code_violations
                         │
                    scraped_parcels (MySQL)
                         │
                    Capital Guardian (Llama 70B)
                    feeds: all fields + raw_html
                    checks: 4 gates + equity + owner lifecycle + permits
                         │
                    assessments (MySQL)
                    decision: BID / DO_NOT_BID / FLAG_LIABILITY
                         │
                    Vibe-Check UI
                    human: KEEP / TRASH
                         │
                    Portfolio Tracker
                    tracks: deployed capital, reserve, subsequent taxes
```

---

## What We Are NOT Building (Explicit Scope Limits)
- No property photos (future AI idea, deferred)
- No automated bidding (human decision required)
- No title search automation (too legally complex)
- No MLS/Zillow scraping (rate limits, legal risk)
- No machine learning (use Llama 70B, not custom models)

---

**Last Updated:** 2026-02-28
**Current Focus:** Preparing for git push, multi-state expansion (Nebraska)
**Next Session:** Layer 4 (financial modeling) + Layer 5 (Vibe-Check Frontend refinements)
