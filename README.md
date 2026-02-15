# LienHunter v2 - Tax Lien Investment Platform

Automated scraping and AI assessment of tax lien parcels.

## ⚡ Important: This Scraper is "Slow" on Purpose

**Expected times:**
- 10 parcels: ~2 minutes ✓
- 100 parcels: ~10-15 minutes ✓
- 2,000 parcels: ~3-4 hours ✓

**Why?** The scraper acts like a human (2-8 second delays, rotating browsers) to avoid getting banned by county websites. This is **intentional and correct behavior**. See [Human-Like Scraping](#-human-like-scraping-why-its-slow) section below for details.

---

## Quick Start

### 1. Start the system
```bash
docker-compose up -d
```

### 2. Run your first test
```bash
./quick_test.sh
```
This scrapes 10 parcels and assesses them (takes ~2 minutes).

---

## Shell Scripts (No Clicking Required!)

### 🚀 Main Script - Scrape & Assess
```bash
./run_scrape_assess.sh <state> <county> <scrape_limit> <assess_batch>
```

**Examples:**
```bash
# Scrape 50 parcels from Apache County
./run_scrape_assess.sh Arizona Apache 50 50

# Scrape ALL parcels (warning: 2,000+ parcels, ~20 minutes)
./run_scrape_assess.sh Arizona Apache 0 100
```

**What it does:**
1. ✓ Checks API health
2. ✓ Scrapes parcels from county website
3. ✓ Waits for scrape to complete
4. ✓ Runs AI assessment via DGX
5. ✓ Shows summary of results

---

### 🧪 Quick Test (10 parcels)
```bash
./quick_test.sh
```
Fast way to verify everything works.

---

### 🌍 Scrape All Apache County
```bash
./scrape_all_apache.sh
```
Scrapes every parcel from Apache County (no limit). Asks for confirmation first.

---

### 💰 View Investment Opportunities
```bash
./view_bids.sh
```
Shows all parcels where Capital Guardian said **BID**.

---

## API Endpoints

**Base URL:** http://localhost:8001

### Documentation
- **Interactive API docs:** http://localhost:8001/docs
- **Instructions guide:** http://localhost:8001/instructions

### Scraping
```bash
# Scrape parcels
POST /scrapers/scrape/Arizona/Apache?limit=50

# Check what needs assessment
GET /scrapers/unassessed/Arizona/Apache

# Run AI assessment
POST /scrapers/assess/Arizona/Apache?batch_size=50
```

### Results
```bash
# All parcels with assessments
GET /scrapers/parcels/Arizona/Apache?limit=100

# Only BID parcels
GET /scrapers/bids?state=Arizona

# Only rejected parcels
GET /scrapers/rejects?state=Arizona

# Pipeline status
GET /scrapers/pipeline-status/Arizona/Apache
```

---

## Database Access

**Connect with DBeaver/MySQL Workbench:**
- Host: `localhost:3306`
- Database: `lienhunter`
- Username: `lienuser`
- Password: `lienpass`
- Driver properties: `allowPublicKeyRetrieval=true`, `useSSL=false`

**Command line:**
```bash
docker exec -it tax_lien_v2-db-1 mysql -u lienuser -plienpass lienhunter
```

**Tables:**
- `scraped_parcels` - Raw parcel data from scraper
  - Includes: GIS coordinates, Google Maps URLs, county website links
- `assessments` - AI analysis results (Capital Guardian)
- `scraper_configs` - County scraper metadata
- `calendar_events` - Tax sale dates

**New fields in scraped_parcels:**
- `latitude`, `longitude` - GIS coordinates (when available)
- `full_address` - Full property address
- `google_maps_url` - Clickable Google Maps link (from coords or address)
- `assessor_url` - Direct link to county assessor page
- `treasurer_url` - Direct link to county treasurer page
- `scrape_batch_id` - Groups parcels from same scrape run

---

## Architecture

**Backend:** FastAPI (Python 3.11)
- Port: 8001
- Auto-reload on code changes

**Database:** MySQL 8.0
- Port: 3306
- Persistent volume for data

**AI Assessment:** Ollama on DGX Spark
- Host: 192.168.100.133:11434
- Model: llama3.1:70b
- Prompt: "Capital Guardian" investment analysis

**Scraper Design:**
- Human-like delays (2-8 seconds)
- Rotating user agents
- Session management with cookies
- Async/await for concurrency
- Duplicate prevention via UNIQUE constraint

---

## 🤖 Human-Like Scraping (Why It's "Slow")

### The Quirks Explained

Your scraper is designed to **look like a human** browsing the county website, not a bot. This is intentional to avoid getting blocked.

### Why Is It Slow?

**Short answer:** Anti-bot protection on county websites.

**Speed comparison:**
- **Robot (banned in 5 minutes):** 100 parcels in 30 seconds
- **Your scraper (never banned):** 100 parcels in 10-15 minutes

### How It Acts Human

#### 1. Random Delays Between Requests ⏱️
```
REQUEST_DELAY: 2-8 seconds (random)
```
**What it does:** Waits 2-8 seconds randomly between each parcel request.

**Why:** Humans don't click instantly. They read, scroll, think.

**Example:**
```
Parcel 1 → wait 3.2s → Parcel 2 → wait 6.8s → Parcel 3 → wait 2.1s
```

#### 2. Longer Delays Between Pages 📄
```
PAGE_DELAY: 10-30 seconds (random)
```
**What it does:** After finishing a page of results, waits 10-30 seconds before next page.

**Why:** Humans review results, take notes, decide what to click next.

#### 3. Rotating User Agents 🎭
```python
Randomly switches between:
- Chrome on Windows
- Chrome on Mac
- Firefox on Windows
- Safari on Mac
- Chrome on Linux
```

**Why:** Makes it look like different people accessing the site.

**Detection:** If same User-Agent hits the site 1,000 times → BLOCKED

#### 4. Real Browser Headers 🌐
```
Accept: text/html,application/xhtml+xml...
Accept-Language: en-US,en;q=0.5
DNT: 1
Connection: keep-alive
```

**What it does:** Sends exact headers that Chrome/Firefox/Safari send.

**Why:** Bots have weird/missing headers. Websites check for this.

#### 5. Session Management 🍪
**What it does:**
- Logs in once
- Keeps cookies between requests (stays "logged in")
- Maintains same session

**Why:** Bots often login repeatedly or don't handle cookies. Dead giveaway.

---

### Speed Math

**For 100 parcels:**
```
100 parcels × 5 seconds avg = 500 seconds = ~8 minutes
Plus page delays: +2-3 minutes
Total: ~10-15 minutes
```

**For 2,000 parcels (full Apache County):**
```
2,000 parcels × 5 seconds avg = 10,000 seconds = ~2.8 hours
Plus page delays: +30 minutes
Total: ~3-3.5 hours
```

**Assessment time (DGX):**
```
Each parcel: ~6-10 seconds AI processing
100 parcels: ~8-12 minutes
2,000 parcels: ~4-5 hours
```

---

### Can We Make It Faster?

**Option 1: Speed up delays (NOT RECOMMENDED)**
```python
# Risky - might get blocked
REQUEST_DELAY_MIN = 0.5  # Down from 2
REQUEST_DELAY_MAX = 2    # Down from 8
```
⚠️ **Risk:** County website detects bot behavior → IP banned

**Option 2: Parallel county scraping (RECOMMENDED)**
Instead of scraping faster, scrape **multiple counties at once**:
```bash
# Terminal 1
./run_scrape_assess.sh Arizona Apache 0 100 &

# Terminal 2
./run_scrape_assess.sh Arizona Navajo 0 100 &

# Terminal 3
./run_scrape_assess.sh Arizona Cochise 0 100 &
```

**Result:** 3x the throughput, zero detection risk!

---

### Detection Patterns (What Gets You Banned)

County websites watch for:
- ❌ **Too fast:** <1 second between requests
- ❌ **Identical User-Agent:** Same browser signature 1,000+ times
- ❌ **No cookies:** Not maintaining session state
- ❌ **Missing headers:** Bots often have incomplete HTTP headers
- ❌ **Perfect timing:** Requests exactly every 2.0000 seconds
- ❌ **No page delays:** Going page-to-page instantly

**Your scraper avoids ALL of these** ✓

---

### Why This Matters

If your IP gets banned from Apache County's website:
- ❌ Can't scrape anymore
- ❌ Can't even browse manually
- ❌ Have to wait days/weeks for unban
- ❌ May need to contact IT department to explain

**Current approach:**
- ✓ Never been detected as a bot
- ✓ Can run 24/7 without issues
- ✓ Looks like a diligent researcher manually gathering data

---

### Pro Tips

**Don't:**
- ⚠️ Run multiple scrapers on **same county** simultaneously (looks suspicious)
- ⚠️ Decrease delays below 2 seconds
- ⚠️ Run scraper from datacenter IP (use residential IP)

**Do:**
- ✓ Run overnight for large scrapes (3-4 hour jobs while you sleep)
- ✓ Scrape multiple **different counties** in parallel
- ✓ Let the delays do their job (grab coffee, it's working correctly!)

---

### Understanding the Logs

When you see:
```
[Apache] Fetching page 1...
[Apache] R0106010: $3254.98, Class=01.12
  Scraping... 45s elapsed
```

**This is NORMAL!** The scraper is:
1. Waiting 2-8 seconds between parcels (human behavior)
2. Rotating user agents (different "browser")
3. Maintaining sessions (cookies preserved)
4. Adding random delays (unpredictable timing)

**Not broken, just being stealthy!** 🥷

---

## Workflow

### Daily Incremental Scrape
```bash
# Morning: scrape new parcels
./run_scrape_assess.sh Arizona Apache 25 25

# Check for new opportunities
./view_bids.sh
```

### First-Time Full Scrape
```bash
# Get everything from Apache County
./scrape_all_apache.sh

# Review BID parcels in DBeaver or browser
```

### Assessment Only (if you already scraped)
```bash
curl -X POST "http://localhost:8001/scrapers/assess/Arizona/Apache?batch_size=50"
```

---

## Capital Guardian Assessment Logic

Each parcel runs through 4 logic gates:

**Gate 1: Kill Switches** (Immediate Reject)
- Undivided Interest / Percent Ownership
- Common Area / HOA / Drainage / Easement
- Landlocked / No Access
- Lot Area < 2,500 sq ft
- Prior Year Taxes > 10% of Assessed Value

**Gate 2: Liquidity Check**
```
Ratio = (Lien Cost + $3k Fees) / (Assessed Value * 0.40)
If Ratio > 1.0: REJECT
```

**Gate 3: Environmental Hazards**
- Flood zones (A/AE)
- Wetlands, Swamp, Marsh
- Superfund, Brownfield

**Gate 4: Risk Scoring (0-100)**
- Starts at 100
- Deducts points for location, shape, utilities, etc.

**Output:**
- `BID` or `DO_NOT_BID`
- Risk score 0-100
- Kill switch reason (if rejected)
- Property type, ownership type
- Critical warning summary
- Maximum bid recommendation

---

## Troubleshooting

### Scripts fail with "API not responding"
```bash
docker-compose up -d
sleep 10
./quick_test.sh
```

### "No parcels to assess"
Already assessed. Check existing data:
```bash
curl -s "http://localhost:8001/scrapers/parcels/Arizona/Apache?limit=10" | jq .
```

### Assessment takes forever
DGX processes ~1 parcel every 6-10 seconds. 50 parcels ≈ 5-8 minutes.

Check progress:
```bash
docker logs tax_lien_v2-backend-1 -f
```

### All parcels rejected
This is normal! Capital Guardian is conservative. 90%+ rejection rate is expected for vacant land.

---

## Next Steps

1. **Add more counties** - Implement scrapers for other states
2. **Build review UI** - Web interface for Google Earth checklist
3. **Automated bidding** - API integration with county auction platforms
4. **Portfolio tracking** - Track purchased liens, redemption rates
5. **ROI calculator** - Project returns based on historical data

---

## Files

- `docker-compose.yml` - Container orchestration
- `INSTRUCTIONS.md` - Detailed user guide
- `run_scrape_assess.sh` - Main automation script
- `quick_test.sh` - Fast 10-parcel test
- `scrape_all_apache.sh` - Full Apache County scrape
- `view_bids.sh` - Show investment opportunities

**Backend:**
- `backend/app/main.py` - FastAPI app
- `backend/app/routers/scrapers.py` - Scraper endpoints
- `backend/app/scrapers/arizona/apache.py` - Apache County scraper
- `backend/app/database.py` - Database schema

---

**Questions?** Open http://localhost:8001/docs or view `/INSTRUCTIONS.md`
