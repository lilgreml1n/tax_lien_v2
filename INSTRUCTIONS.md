# LienHunter v2 - Quick Start Guide

## Overview
Tax lien investment platform with 2-phase pipeline:
1. **Scrape** - Pull raw parcel data + generate clickable review links
2. **Assess** - Run AI analysis via DGX Ollama (Capital Guardian)
3. **Review** - Human clicks links (Maps, Street View, Zillow, Assessor) for final approval

## ✨ What's New - Phase 1A
Every parcel now includes **clickable links** for human review:
- 🗺️ **Google Maps** - Property location
- 👁️ **Street View** - Visual property inspection
- 💰 **Zillow** - Estimated market value
- 🏠 **Realtor.com** - Property listings
- 🏛️ **County Assessor** - Full property details
- 💵 **County Treasurer** - Tax payment info

Plus extraction attempts for:
- Lot size, zoning, assessed values, legal description (when publicly available)

---

## Quick Start - Apache County, Arizona

### Step 1: Scrape Parcels
Pull raw parcel data from Apache County website:

```bash
POST /scrapers/scrape/Arizona/Apache?limit=50
```

**What this does:**
- Logs into Apache County Treasurer & Assessor websites
- Scrapes parcel ID, billed amount, legal class, address
- Saves raw data to `scraped_parcels` table
- Runs in background (returns immediately)

**Parameters:**
- `limit` - How many parcels to scrape (default: 10)

**Response:**
```json
{
  "job_id": "scrape_Arizona_Apache_1771109206",
  "status": "scraping",
  "started_at": "2026-02-14T22:46:46"
}
```

---

### Step 2: Check What Needs Assessment

```bash
GET /scrapers/unassessed/Arizona/Apache
```

**Response:**
```json
{
  "unassessed_count": 9,
  "sample": [
    {
      "id": 11,
      "parcel_id": "R0009222",
      "billed_amount": 93.94,
      "legal_class": "02.R"
    }
  ]
}
```

---

### Step 3: Run AI Assessment (DGX)

```bash
POST /scrapers/assess/Arizona/Apache?batch_size=20
```

**What this does:**
- Pulls unassessed parcels from database
- Sends each to DGX machine (192.168.100.133:11434)
- Uses llama3.1:70b model with "Capital Guardian" prompt
- Parses structured output: BID/DO_NOT_BID, risk score, kill switches
- Saves to `assessments` table
- Runs in background

**Parameters:**
- `batch_size` - How many to assess in this batch (default: 10)

**Response:**
```json
{
  "job_id": "assess_Arizona_Apache_1771109299",
  "status": "assessing (9 pending)",
  "started_at": "2026-02-14T22:48:19"
}
```

---

## Viewing Results

### Option 1: View All Parcels with Assessments

```bash
GET /scrapers/parcels/Arizona/Apache?limit=100
```

**Returns:** All scraped parcels joined with assessment data

**Key fields:**
- `parcel_id` - County parcel identifier
- `billed_amount` - Tax amount owed
- `decision` - BID or DO_NOT_BID
- `risk_score` - 0-100 (higher = safer investment)
- `kill_switch` - Why it was rejected (if DO_NOT_BID)
- `critical_warning` - Biggest risk summary
- `property_type` - vacant land, single-family, etc.
- `ownership_type` - individual, LLC, trust, etc.

**NEW - Review Links (Phase 1A):**
- `google_maps_url` - Property location on map
- `street_view_url` - Google Street View (visual inspection)
- `zillow_url` - Zillow property page (value estimate)
- `realtor_url` - Realtor.com property page
- `assessor_url` - County assessor (full details)
- `treasurer_url` - County treasurer (tax info)

**NEW - Property Data (when available):**
- `lot_size_acres` - Parcel size in acres
- `lot_size_sqft` - Parcel size in square feet
- `zoning_code` - Zoning designation (R-1, C-1, etc.)
- `zoning_description` - Zoning description
- `assessed_land_value` - County assessed land value
- `assessed_improvement_value` - County assessed improvement value
- `assessed_total_value` - Total assessed value
- `legal_description` - Legal property description
- `latitude`, `longitude` - GIS coordinates (when available)

---

### Option 2: View Only BID Opportunities

```bash
GET /scrapers/bids?state=Arizona&limit=100
```

**Returns:** Only parcels where Capital Guardian said **BID**

These are investment opportunities that passed all 4 logic gates:
- ✅ No kill switches (title, access, size issues)
- ✅ Passed liquidity check (cost < 40% of assessed value)
- ✅ No environmental hazards (FEMA flood zones, wetlands)
- ✅ Risk score > 0

---

### Option 3: View Rejected Parcels

```bash
GET /scrapers/rejects?state=Arizona&limit=100
```

**Returns:** Parcels that failed assessment with rejection reasons

**Common kill switches:**
- Undivided Interest (don't own 100% fee simple title)
- Common Area / HOA / Drainage (scrap land)
- Landlocked / No Access
- Lot Area < 2,500 sq ft
- Prior Year Taxes > 10% of Assessed Value

---

### Option 4: Pipeline Status Overview

```bash
GET /scrapers/pipeline-status/Arizona/Apache
```

**Returns:**
```json
{
  "scraped": 12,
  "assessed": 10,
  "bids": 0,
  "reviewed": 0,
  "approved": 0
}
```

Quick snapshot of where parcels are in the pipeline.

---

## Capital Guardian Assessment Logic

The AI runs each parcel through 4 sequential gates:

### Gate 1: Kill Switches (Immediate Reject)
1. Undivided Interest or Percent Interest
2. Common Area, HOA, Drainage, Easement, Private Road
3. Landlocked or No Access
4. Lot Area < 2,500 sq ft (unless commercial)
5. Lot Width < 40 ft
6. Prior Year Taxes > 10% of Assessed Value

**If ANY trigger:** `DO_NOT_BID` + stop

---

### Gate 2: Liquidity Check
```
Liquidity Ratio = (Total Lien Cost + $3000 Fees) / (Assessed Value * 0.40)
```

Fire sale = 40% of assessed value
- **Ratio > 1.0:** REJECT (cost exceeds fire sale)
- **Ratio < 1.0:** Pass to Gate 3

---

### Gate 3: Environmental Hazards
Scans for:
- Flood Zone A/AE
- Wetlands, Swamp, Marsh
- Superfund, Brownfield, Industrial waste

**If ANY found:** REJECT

---

### Gate 4: Risk Scoring (0-100)
Starts at 100, deducts points:
- (-20) Outside major metro (>30 miles)
- (-15) Vacant land with no utilities
- (-10) Owner is LLC
- (-30) Irregular or Triangle shape
- (-50) Slope or Steep terrain

**Final score determines investment grade**

---

## Review Workflow (for BID parcels)

### 1. Get Review Queue

```bash
GET /scrapers/bids?limit=50
```

Get all BID parcels that need human review.

---

### 2. Manual Checklist (Google Earth review)

For each BID parcel, verify:
- [ ] Street view - property visible, good condition
- [ ] Power lines - utilities nearby
- [ ] Topography - flat, buildable terrain
- [ ] Water test - well feasibility
- [ ] Access/frontage - road access confirmed
- [ ] Rooftop count - development density

---

### 3. Final Boss Approval

Last checks before purchase:
- [ ] Legal description matches map
- [ ] No hidden structures (liability)
- [ ] Who cuts grass? (indicates abandonment)

If all pass → **APPROVED TO BID**

---

## Database Access

**Connection Info:**
- Host: `localhost:3306`
- Database: `lienhunter`
- User: `lienuser`
- Password: `lienpass`

**Key Tables:**
- `scraped_parcels` - Raw scrape data
- `assessments` - AI analysis results
- `scraper_configs` - County scraper metadata
- `calendar_events` - Tax sale dates

**Direct access:**
```bash
docker exec -it tax_lien_v2-db-1 mysql -u lienuser -plienpass lienhunter
```

---

## API Documentation

**Interactive Swagger UI:**
```
http://localhost:8001/docs
```

**View these instructions:**
```
http://localhost:8001/instructions
```

---

## Common Workflows

### Workflow 1: First-time county scrape
```bash
# 1. Scrape 50 parcels (generates all clickable links automatically)
POST /scrapers/scrape/Arizona/Apache?limit=50

# 2. Wait 1-2 minutes for scrape to complete

# 3. Check how many need assessment
GET /scrapers/unassessed/Arizona/Apache

# 4. Assess all unassessed
POST /scrapers/assess/Arizona/Apache?batch_size=50

# 5. Wait for DGX to complete (2-3 min per 10 parcels)

# 6. View results with all review links
GET /scrapers/parcels/Arizona/Apache?limit=100

# 7. For BID parcels - click links to review:
#    - Street View: Visual inspection
#    - Zillow: Get value estimate
#    - Assessor: See full property details
#    - Google Maps: Verify location
```

---

### Workflow 2: Daily incremental scrape
```bash
# Scrape new parcels (checks for duplicates)
POST /scrapers/scrape/Arizona/Apache?limit=25

# Auto-assess anything new
POST /scrapers/assess/Arizona/Apache?batch_size=25

# Check for new BID opportunities
GET /scrapers/bids?state=Arizona
```

---

### Workflow 3: Review BID parcels
```bash
# Get all BID parcels
GET /scrapers/bids

# For each parcel:
# - Open in Google Earth (use address)
# - Complete visual checklist
# - Submit review via /review endpoint (see /docs)

# Get approved parcels ready to purchase
GET /review/approved
```

---

## Troubleshooting

**No unassessed parcels found:**
- Check if scraper completed: `GET /scrapers/parcels/Arizona/Apache`
- Parcels may already be assessed from previous run

**Assessment takes too long:**
- DGX processes 1 parcel every 6-10 seconds
- 50 parcels ≈ 5-8 minutes
- Check backend logs: `docker logs tax_lien_v2-backend-1 -f`

**Scraper returns 0 results:**
- County website may be down
- Login credentials expired (check scraper code)
- Already scraped all available parcels

**All parcels rejected (DO_NOT_BID):**
- This is normal! Capital Guardian is conservative
- Most tax lien parcels have serious issues
- ~90% rejection rate is expected for vacant land

---

## Architecture Notes

**Backend:** FastAPI (port 8001)
**Database:** MySQL 8.0 (port 3306)
**AI Assessment:** Ollama on DGX Spark (192.168.100.133:11434)
**Model:** llama3.1:70b

**Scraper design:**
- Human-like delays (2-8 seconds between requests)
- Rotating user agents
- Session management with cookies
- Async/await for concurrency

**Assessment design:**
- Synchronous (one at a time to avoid DGX overload)
- Structured prompt with required output format
- Regex parsing for decision/score/kill_switch fields
- Saves full response + parsed fields

---

## Example API Response (Enhanced)

```json
{
  "parcel_id": "R0106010",
  "billed_amount": 3254.98,
  "legal_class": "01.12",

  // AI Assessment
  "decision": "DO_NOT_BID",
  "risk_score": 0,
  "kill_switch": "Undivided Interest",
  "critical_warning": "No clear title information",

  // Clickable Review Links (NEW!)
  "google_maps_url": "https://www.google.com/maps/search/?api=1&query=Parcel+R0106010+Apache+County+Arizona",
  "street_view_url": "https://www.google.com/maps/@?api=1&map_action=pano...",
  "zillow_url": "https://www.zillow.com/homes/Parcel-R0106010-Apache-County-AZ_rb/",
  "realtor_url": "https://www.realtor.com/realestateandhomes-search/Apache-County_AZ/parcel-R0106010",
  "assessor_url": "https://eagleassessor.co.apache.az.us/assessor/taxweb/account.jsp?accountNum=R0106010",
  "treasurer_url": "https://eagletreasurer.co.apache.az.us:8443/treasurer/treasurerweb/account.jsp?account=R0106010",

  // Property Details (when available from county)
  "lot_size_acres": 2.5,
  "lot_size_sqft": 108900,
  "zoning_code": "R-1",
  "zoning_description": "Single Family Residential",
  "assessed_total_value": 15000.00,
  "latitude": 34.567890,
  "longitude": -109.123456
}
```

**Note:** Property detail fields (lot size, zoning, values) depend on what the county publishes publicly. Apache County has limited public data, but all review links are generated for manual inspection.

---

## Human Review Workflow

For parcels Capital Guardian says **BID** or **INVESTIGATE**:

1. **Click Street View URL** → See the property visually
2. **Click Zillow URL** → Get estimated market value
3. **Click Assessor URL** → See full county property details
4. **Click Google Maps URL** → Verify location and nearby area
5. **Make final decision** → Approve or reject for bidding

**All links open in new tab - easy point-and-click review!**

---

## Important Notes

### Data Availability by County
- **Apache County, AZ:** Limited public data (basic tax info only)
  - ✅ Generates all review links
  - ⚠️ Lot size, zoning, values not on public pages
  - 👍 Humans can click Assessor URL to see full details

- **Better Counties (Future):**
  - Florida counties: Full property data public
  - Texas counties: Detailed GIS APIs
  - Illinois (Cook): Comprehensive public records
  - When we add these: Full automation possible!

### No External API Calls (by design)
- Street View URL = link only (no image fetch)
- Zillow URL = link only (no API call)
- Realtor URL = link only (no scraping)
- **Result:** Zero rate limits, zero bandwidth issues
- **Humans click when needed** = selective, smart usage

---

## Next Steps

1. ✅ **Phase 1A Complete** - Clickable links for all parcels
2. **Build review UI** - Web interface with click-to-open buttons
3. **Add better counties** - Florida, Texas scrapers (full data)
4. **AI visual analysis** - Automate Street View inspection (future)
5. **Portfolio tracking** - Track purchased liens, redemption status
6. **Automated bidding** - API integration with county auction platforms

---

**Questions?** Check `/docs` for full API reference or view source code.
