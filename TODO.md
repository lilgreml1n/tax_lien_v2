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

### Notifications & Alerts
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
