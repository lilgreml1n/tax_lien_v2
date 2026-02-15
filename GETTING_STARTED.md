# LienHunter v2 - Getting Started Guide

Welcome! This guide will get you up and running with the LienHunter v2 tax lien investment platform.

---

## 📋 Table of Contents

1. [What Is This?](#what-is-this)
2. [Quick Start (5 Minutes)](#quick-start-5-minutes)
3. [Understanding the System](#understanding-the-system)
4. [Running Your First Scrape](#running-your-first-scrape)
5. [Time Expectations](#time-expectations)
6. [Viewing Results](#viewing-results)
7. [Daily Workflow](#daily-workflow)
8. [Troubleshooting](#troubleshooting)

---

## What Is This?

LienHunter v2 is an **automated tax lien investment research platform** that:

1. **Scrapes** tax lien data from county websites
2. **Assesses** each property using AI (Capital Guardian on DGX)
3. **Generates clickable review links** (Google Maps, Street View, Zillow, etc.)
4. **Recommends** which liens to bid on vs avoid

**Goal:** Find profitable tax lien investments while filtering out bad deals automatically.

---

## Quick Start (5 Minutes)

### Step 1: Start the System
```bash
cd /Users/raven/Documents/CURRENT_PROJECTS/tax_lien_v2
docker-compose up -d
```

Wait 10 seconds for containers to start.

### Step 2: Verify System is Running
```bash
./status.sh
```

You should see:
```
✓ Docker Containers: Running
✓ API: Healthy
```

### Step 3: Run a Quick Test
```bash
./quick_test.sh
```

This will:
- Scrape 10 parcels from Apache County
- Assess them via AI
- Show results
- **Takes ~2 minutes**

### Step 4: View Results
```bash
./view_bids.sh
```

Or open in browser:
```
http://localhost:8001/docs
```

**That's it! You're up and running.** ✅

---

## Understanding the System

### The 3-Phase Pipeline

```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│  1. SCRAPE  │ -->  │  2. ASSESS   │ -->  │  3. REVIEW  │
└─────────────┘      └──────────────┘      └─────────────┘
     ~4-5h              ~5-6h                  Manual
```

#### Phase 1: Scrape
- Visits Apache County tax lien website
- Extracts parcel data (ID, tax amount, legal class)
- Generates review links (Maps, Street View, Zillow, etc.)
- **Acts like a human** (2-8 second delays to avoid bans)

#### Phase 2: Assess (AI)
- Sends each parcel to DGX machine
- AI model: llama3.1:70b (70 billion parameters)
- Uses "Capital Guardian" investment analysis prompt
- Decides: BID or DO_NOT_BID
- **Typically 90% rejection rate** (this is good - filters junk)

#### Phase 3: Review (Human)
- You click review links for BID parcels
- Visual inspection via Street View
- Check value on Zillow
- Verify details on County Assessor
- Make final go/no-go decision

---

## Running Your First Scrape

### Option 1: Quick Test (Recommended First)
```bash
./quick_test.sh
```
- **Parcels:** 10
- **Time:** ~2 minutes
- **Purpose:** Verify everything works

### Option 2: Small Batch
```bash
./run_scrape_assess.sh Arizona Apache 50 50
```
- **Parcels:** 50
- **Time:** ~10-15 minutes
- **Purpose:** Get meaningful results quickly

### Option 3: Medium Batch
```bash
./run_scrape_assess.sh Arizona Apache 200 200
```
- **Parcels:** 200
- **Time:** ~1 hour
- **Purpose:** Daily/weekly scraping

### Option 4: Get Everything
```bash
./scrape_all_apache.sh
```
- **Parcels:** ~2,000 (all available)
- **Time:** ~9-11 hours
- **Purpose:** Complete database, run overnight

---

## Time Expectations

### Why Is It "Slow"?

The scraper **acts like a human** to avoid getting banned:
- Random 2-8 second delays between requests
- Random 10-30 second delays between pages
- Rotating browser signatures
- Session management with cookies

**This is intentional and correct behavior!**

### Scraping Times

| Parcels | Scrape Time | Assess Time | Total |
|---------|-------------|-------------|-------|
| 10 | 1 min | 1 min | **2 min** |
| 50 | 5 min | 8 min | **13 min** |
| 100 | 10 min | 15 min | **25 min** |
| 500 | 50 min | 80 min | **2 hours** |
| 2,000 | 4-5 hours | 5-6 hours | **9-11 hours** |

### Speed Breakdown

**Per Parcel:**
- Scrape: ~6 seconds
- Assess: ~10 seconds
- Total: ~16 seconds per parcel

**Why Assessment Takes Longer:**
- DGX runs llama3.1:70b (large model)
- Analyzes property through 4 logic gates
- Generates structured investment decision

### Running Overnight

**Perfect for full scrapes:**
```bash
# Friday 8pm - start
./scrape_all_apache.sh

# Saturday 7am - done!
./view_bids.sh
```

**Or use nohup:**
```bash
nohup ./scrape_all_apache.sh > scrape.log 2>&1 &

# Check progress
tail -f scrape.log
```

---

## Viewing Results

### Quick View - Shell Script
```bash
./view_bids.sh
```
Shows all BID parcels in terminal.

### System Status
```bash
./status.sh
```
Shows:
- Container health
- Database statistics
- Parcel counts by county

### Browser (Interactive)

**API Documentation:**
```
http://localhost:8001/docs
```

**View All Parcels:**
```
GET http://localhost:8001/scrapers/parcels/Arizona/Apache?limit=100
```

**View BID Parcels Only:**
```
GET http://localhost:8001/scrapers/bids?state=Arizona
```

**View Rejected Parcels:**
```
GET http://localhost:8001/scrapers/rejects?state=Arizona
```

### Database (DBeaver)

**Connection:**
- Host: `localhost:3306`
- Database: `lienhunter`
- User: `lienuser`
- Password: `lienpass`
- Driver properties: `allowPublicKeyRetrieval=true`, `useSSL=false`

**Useful Queries:**
```sql
-- See all BID parcels
SELECT * FROM scraped_parcels sp
JOIN assessments a ON a.parcel_id = sp.id
WHERE a.decision = 'BID'
ORDER BY a.risk_score DESC;

-- Count by decision
SELECT decision, COUNT(*)
FROM assessments
GROUP BY decision;

-- Check scraping progress
SELECT
  COUNT(*) as total,
  COUNT(CASE WHEN assessment_status='assessed' THEN 1 END) as assessed
FROM scraped_parcels;
```

---

## Daily Workflow

### Morning Routine (5 minutes)
```bash
# 1. Check system status
./status.sh

# 2. View new BID opportunities
./view_bids.sh

# 3. Review in browser
open http://localhost:8001/docs
```

### Weekly Scraping (1-2 hours)
```bash
# Scrape new/updated parcels
./run_scrape_assess.sh Arizona Apache 100 100

# Wait for completion, then review
./view_bids.sh
```

### Monthly Deep Dive (overnight)
```bash
# Full county scrape (finds everything)
./scrape_all_apache.sh
```

### Reviewing BID Parcels

For each BID parcel, click through:

1. **Street View URL** → See the property
   - Is it vacant land or improved?
   - Any visible structures?
   - Road access visible?

2. **Zillow URL** → Get value estimate
   - What's it worth?
   - Recent sales nearby?

3. **Assessor URL** → See full details
   - Lot size
   - Zoning
   - Assessed value

4. **Google Maps URL** → Verify location
   - How far from town?
   - Neighborhood quality?

5. **Make decision** → Bid or pass

---

## Understanding Results

### Capital Guardian Decisions

**BID** - Good investment opportunity
- Passed all 4 logic gates
- No kill switches triggered
- Positive risk/reward ratio
- **~10% of parcels**

**DO_NOT_BID** - Avoid
- Kill switch triggered (title issues, size, access)
- OR failed liquidity check
- OR environmental hazards
- OR low risk score
- **~90% of parcels**

### Common Rejection Reasons

| Kill Switch | What It Means |
|-------------|---------------|
| Undivided Interest | Don't own 100% of property |
| Common Area | HOA land, easement, drainage |
| Landlocked | No road access |
| Lot Area < 2,500 sqft | Too small to build on |
| Prior Taxes > 10% of Value | Special assessments or fines |

**This is GOOD!** Capital Guardian filters out bad deals automatically.

### Example Results

From 100 parcels scraped:
- **90 parcels** → DO_NOT_BID (filtered out)
- **10 parcels** → BID or INVESTIGATE (worth reviewing)
- **2-3 parcels** → Actually bid on (after human review)

**That's normal and expected!**

---

## Shell Scripts Reference

| Script | Use Case | Time |
|--------|----------|------|
| `./status.sh` | Check system health | Instant |
| `./quick_test.sh` | Test everything works | 2 min |
| `./run_scrape_assess.sh <state> <county> <limit> <batch>` | Custom scrape | Varies |
| `./scrape_all_apache.sh` | Get everything | 9-11 hours |
| `./view_bids.sh` | See BID parcels | Instant |
| `./update_existing_parcels.sh` | Add URLs to old data | 1 min |

### Script Parameters

**run_scrape_assess.sh:**
```bash
./run_scrape_assess.sh <state> <county> <scrape_limit> <assess_batch>
```

Examples:
```bash
# Scrape 50, assess 50
./run_scrape_assess.sh Arizona Apache 50 50

# Scrape ALL (0=no limit), assess in batches of 100
./run_scrape_assess.sh Arizona Apache 0 100
```

---

## Troubleshooting

### "API not responding"
```bash
docker-compose up -d
sleep 10
./status.sh
```

### "No parcels scraped"
- County website might be down
- Check logs: `docker logs tax_lien_v2-backend-1 -f`
- Try again in 10 minutes

### "All parcels rejected"
- **This is normal!** 90% rejection rate expected
- Capital Guardian is conservative
- Most tax lien properties have serious issues

### "Scraper is slow"
- **This is intentional!** Human-like delays prevent bans
- 2-8 second delays are correct behavior
- See: "Why Is It Slow?" section above

### "Assessment takes forever"
- DGX processes ~1 parcel every 8-10 seconds
- 100 parcels = ~15 minutes
- This is normal for 70B parameter model

### Check Logs
```bash
# Backend logs
docker logs tax_lien_v2-backend-1 -f

# Just errors
docker logs tax_lien_v2-backend-1 2>&1 | grep -i error

# Database logs
docker logs tax_lien_v2-db-1
```

---

## Next Steps

### After Your First Scrape

1. **Review documentation:**
   - http://localhost:8001/instructions
   - http://localhost:8001/readme

2. **Explore the API:**
   - http://localhost:8001/docs

3. **Query the database:**
   - Connect with DBeaver
   - Run sample queries

4. **Set up routine:**
   - Weekly scrapes (100-200 parcels)
   - Monthly full scrapes (overnight)

### Advanced Usage

- **Add more counties** (when scrapers ready)
- **Build custom frontend** (all APIs ready)
- **Export to Excel** (use API + scripting)
- **Set up notifications** (future feature)

---

## Important Links

**FastAPI Docs:**
- Interactive API: http://localhost:8001/docs
- Instructions: http://localhost:8001/instructions
- README: http://localhost:8001/readme

**Documentation Files:**
- `README.md` - Complete guide + human-like scraping
- `INSTRUCTIONS.md` - Quick start + API reference
- `GIS_MAPPING.md` - Mapping features deep dive
- `TODO.md` - Future features roadmap
- `ENHANCEMENT_ROADMAP.md` - Long-term vision

**Database:**
- Host: localhost:3306
- Database: lienhunter
- User: lienuser
- Password: lienpass

---

## Key Concepts

### Human-Like Scraping
- **2-8 second delays** between requests
- **10-30 second delays** between pages
- **Rotating browser signatures**
- Prevents IP bans from county websites

### Capital Guardian AI
- **4 logic gates:** Kill switches, Liquidity, Hazards, Risk scoring
- **Conservative by design:** Prevents capital loss
- **90% rejection rate:** Filters out bad deals
- **DGX-powered:** llama3.1:70b model

### Clickable Review Links
- **6 URLs per parcel:** Maps, Street View, Zillow, Realtor, Assessor, Treasurer
- **No API calls:** Just URLs (click when needed)
- **Zero rate limits:** Smart, selective usage

### Two-Tier Data
- **Tier 1 (Apache County):** Basic data + review links
- **Tier 2 (Future counties):** Full property data extraction
- Different counties publish different levels of detail

---

## Support

**Questions?**
- Check `/docs` endpoint
- Review README.md
- Read INSTRUCTIONS.md
- Consult TODO.md for planned features

**Issues?**
- Check logs: `docker logs tax_lien_v2-backend-1`
- Run status check: `./status.sh`
- Restart containers: `docker-compose restart`

---

## Quick Reference Card

```bash
# Start system
docker-compose up -d

# Check status
./status.sh

# Quick test (2 min)
./quick_test.sh

# Medium batch (1 hour)
./run_scrape_assess.sh Arizona Apache 200 200

# Full scrape (overnight)
./scrape_all_apache.sh

# View results
./view_bids.sh
# OR
open http://localhost:8001/docs

# Stop system
docker-compose down
```

---

**Ready to find profitable tax liens? Start with:**
```bash
./quick_test.sh
```

**Good luck!** 💰🚀
