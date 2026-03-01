# LienHunter v2 - TODO List

## 🔥 Phase 1A - DONE ✅
- [x] Add GIS coordinates (lat/lon)
- [x] Add Google Maps URLs (clickable)
- [x] Add Street View URLs (clickable)
- [x] Add Zillow URLs (clickable)
- [x] Add Realtor.com URLs (clickable)
- [x] Extract lot size (acres + sqft)
- [x] Extract zoning code + description
- [x] Extract assessed values (land/improvement/total)
- [x] Extract legal description
- [x] Update database schema
- [x] Update Apache scraper
- [x] Update API endpoints

---

## 📸 Visual Property Analysis (FUTURE - AI Ideas Coming)

### Property Photos/Images - **HOLD FOR NOW**
- [ ] Google Street View image fetching (API)
- [ ] County GIS aerial imagery download
- [ ] Property photos from Zillow/Realtor
- [ ] Image storage strategy (S3, local, CDN?)
- [ ] Thumbnail generation

### AI Visual Analysis - **YOUR SECRET SAUCE** 🤖
- [ ] AI property condition assessment from images
- [ ] Automated visual checklist (roof, structure, vegetation)
- [ ] Detect improvements (buildings, pools, fences)
- [ ] Flag hazards (debris, damaged structures)
- [ ] Compare Street View timeline (property condition over time)
- [ ] GPT-4 Vision or similar for visual AI analysis

**Notes:**
- Wait until other parts figured out first
- User has AI ideas for automation
- Focus on clickable links for human review now
- Property photo analysis comes later

## 🚀 Deployment & Git Preparation
- [x] Create `.env.sample`
- [x] Update `README.md` with multi-state support and frontend
- [x] Update `ASSESSMENT_PLAYBOOK.md` with current logic
- [x] Stage and commit all v2 changes for git push
- [ ] Push to remote repository

---

## 🔥 Immediate Next - Layer 1 + 2 + 4 (PLAN.md)

### Layer 1: Data Completeness ✅ DONE
Files updated:
- [x] `backend/app/database.py` - Added all 13 missing columns to `scraped_parcels` CREATE TABLE + idempotent ALTER TABLE migrations
- [x] `backend/app/routers/scrapers.py` - SELECT query in assessment now fetches all fields
- [ ] `backend/app/scrapers/arizona/apache.py` - Store `raw_html` (deferred - assessor regexes not matching Apache HTML yet)

### Layer 2: Smarter Capital Guardian Prompt ✅ DONE
Files updated:
- [x] `backend/app/routers/scrapers.py` - Major overhaul:
  - ALL Gate 1 checks moved to Python (no LLM hallucination on N/A data)
  - Python short-circuit: rejected parcels skip LLM call entirely (2-3x faster for rejects)
  - Estate of / Heirs detection (estate_flag)
  - Absentee owner detection (mailing_differs)
  - Shack detection (improvement < $10k, only if known)
  - Lot too small (< 2,500 sqft, only if known)
  - Liquidity check Gate 2 in Python
  - Legal description keyword scan in Python (kill words + environmental)
  - Bankruptcy/IRS scan in Python
  - Legal class kill switch in Python
  - Model updated to `llama3.1:70b` (from 8b)
  - LLM now only handles scoring (Gate 4) for parcels that survive Python gates

### Layer 4: Financial Modeling
Files to update:
- [ ] `backend/app/database.py` - Add columns:
  - `projected_annual_cost` (estimated year 2 tax)
  - `reserve_required` (lien_amount × 0.30)
  - `total_holding_cost` (lien + reserve + projected year 2)
- [ ] `backend/app/routers/scrapers.py` - Add portfolio endpoint:
  - `GET /scrapers/portfolio` - total deployed, reserve used, available capital
  - Enforce: never recommend BID if it would exceed $35k deployed (70% of $50k)

---

## 🔴 High Priority - Next Steps

### Enhanced Research (BID parcels only)
- [ ] FEMA Flood Zone API integration
  - Only call for parcels with BID/INVESTIGATE decision
  - Cache results to avoid re-checking
  - Database field: `fema_flood_zone`, `is_flood_risk`

- [ ] Environmental hazards
  - EPA Superfund proximity check
  - Wetlands designation
  - Database fields: `superfund_distance_miles`, `is_wetland`

- [ ] Distance to city center
  - Calculate miles to nearest major city
  - Flag if >30 miles (Capital Guardian deduction)
  - Database fields: `distance_to_city_miles`, `nearest_city`

### Comparable Sales (selective)
- [ ] Zillow API integration (if available)
- [ ] Realtor.com scraping (careful with rate limits)
- [ ] Store as JSON array in database
- [ ] Only fetch for properties passing initial assessment

---

## 🟡 Medium Priority

### Tax Sale Calendar
- [ ] Extract auction dates from county websites
- [ ] Store in `calendar_events` table (already exists)
- [ ] Link parcels to auction events
- [ ] Add fields to `scraped_parcels`:
  - `auction_date`
  - `auction_type` (online/in-person)
  - `auction_platform_url`
  - `registration_deadline`
  - `deposit_required`

### Multi-County Expansion
- [ ] Navajo County, AZ scraper
- [ ] Cochise County, AZ scraper
- [ ] Yavapai County, AZ scraper
- [ ] Template for creating new county scrapers
- [ ] Automated scraper testing framework

---

## 🟢 Lower Priority / Nice to Have

### Portfolio Management
- [ ] Create `bids` table (track bid history)
- [ ] Create `watchlist` table (mark parcels to monitor)
- [ ] Create `owned_liens` table (track purchased liens)
- [ ] Redemption tracking and interest calculations
- [ ] ROI calculator per parcel

### Notifications & Alerts 🔔
- [ ] **Discord Webhook Notifications** ← HIGH PRIORITY
  - Scrape job started / completed (with parcel count)
  - Scrape crashed / auto-resumed (with error reason)
  - Assessment complete (BID count, DO_NOT_BID count, top opportunities)
  - New BID parcels found (parcel ID, amount, score, assessor link)
  - Daily summary report (total scraped, assessed, BID count)
  - Uses Discord Webhooks (no bot needed, just a URL in config)
- [ ] Email alerts for new BID parcels
- [ ] SMS alerts for high-value opportunities
- [ ] Auction reminder notifications (7 days, 1 day before)
- [ ] Price drop alerts

### Analytics & Reporting
- [ ] County market trend analysis
- [ ] Historical redemption rates by area
- [ ] ROI projections and forecasts
- [ ] Export to Excel/CSV
- [ ] Dashboard with charts

### Advanced Features
- [ ] Property boundary GeoJSON polygons
- [ ] School district ratings
- [ ] Crime statistics by area
- [ ] Population growth trends
- [ ] Parcel shape analysis (flag irregular shapes)

---

## 🛠️ Technical Debt

### Code Quality
- [ ] Add comprehensive unit tests
- [ ] Add integration tests for scrapers
- [ ] Error handling improvements
- [ ] Logging framework (structured logs)
- [ ] Code documentation (docstrings)

### Performance
- [ ] Database indexing optimization
- [ ] Query performance tuning
- [ ] Caching layer (Redis?)
- [ ] Async API endpoints where beneficial

### DevOps
- [ ] CI/CD pipeline setup
- [ ] Automated deployments
- [ ] Database backups
- [ ] Monitoring & alerting (Sentry, DataDog)
- [ ] Rate limiting on API endpoints

---

## 📝 Documentation Needs

- [ ] API endpoint comprehensive documentation
- [ ] Scraper development guide
- [ ] Database schema diagram
- [ ] Deployment guide (production)
- [ ] User manual for frontend (when built)

---

## 🎨 Frontend (Future)

- [ ] React/Vue dashboard
- [ ] Parcel details view with all clickable links
- [ ] Google Maps integration (embedded)
- [ ] Image gallery (when photos implemented)
- [ ] Filtering and sorting
- [ ] Export results
- [ ] Mobile responsive design

---

## 💡 Research / Exploration

- [ ] Machine learning for redemption probability
- [ ] Historical data analysis for better risk scoring
- [ ] Automated bidding strategy optimization
- [ ] Title search API integrations
- [ ] County GIS API access (where available)

---

**Last Updated:** 2026-02-14
**Current Focus:** Phase 1A complete, ready for testing ✅
