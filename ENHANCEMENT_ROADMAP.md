# LienHunter v2 - Enhancement Roadmap

## 🎯 Vision
Transform from basic scraper → **Complete Tax Lien Investment Intelligence Platform**

---

## Phase 1: Property Intelligence (PRIORITY)

### 1.1 Visual Assessment 📸
**Goal:** See the property without leaving your desk

- [ ] **Google Street View URL**
  - Auto-generate Street View link from coordinates/address
  - Fallback to parcel search if no exact location
  - Database field: `street_view_url`

- [ ] **County GIS Aerial Image**
  - Extract aerial photo URL from county GIS
  - Cache image URL in DB for quick access
  - Database field: `aerial_image_url`

- [ ] **Property Photos API**
  - Integrate Google Places Photos API
  - Or Zillow/Realtor.com image scraping
  - Database field: `property_image_urls` (JSON array)

**Impact:** 🔥🔥🔥 HIGH - Visual inspection is critical for land investing

---

### 1.2 Property Characteristics 📊
**Goal:** Know what you're buying

- [ ] **Lot Size**
  - Scrape acreage from assessor
  - Validate against legal description
  - Database field: `lot_size_acres`, `lot_size_sqft`

- [ ] **Zoning**
  - Extract zoning code from assessor
  - Lookup zoning description (residential, commercial, agricultural)
  - Database fields: `zoning_code`, `zoning_description`

- [ ] **Utilities Available**
  - Parse assessor page for: water, sewer, electric, gas
  - Flag as boolean fields
  - Database fields: `has_water`, `has_sewer`, `has_electric`, `has_gas`

- [ ] **Land Use**
  - Current use: vacant, improved, agricultural
  - Database field: `land_use`

- [ ] **Legal Description**
  - Full legal description text
  - Parse for: section, township, range
  - Database fields: `legal_description`, `section`, `township`, `range`

**Impact:** 🔥🔥🔥 HIGH - Essential for Capital Guardian AI to make better decisions

---

### 1.3 Valuation Data 💰
**Goal:** Know if the lien cost < property value

- [ ] **Assessed Value**
  - Land value
  - Improvement value
  - Total value
  - Database fields: `assessed_land_value`, `assessed_improvement_value`, `assessed_total_value`

- [ ] **Market Value Estimates**
  - Zillow Zestimate (if available)
  - Realtor.com estimate
  - County appraised value
  - Database fields: `zillow_estimate`, `realtor_estimate`, `market_value`

- [ ] **Zillow/Realtor URLs**
  - Auto-generate property page links
  - Database fields: `zillow_url`, `realtor_url`

- [ ] **Comparable Sales**
  - Find 3-5 recent sales nearby
  - Store as JSON: `[{address, price, date, distance}]`
  - Database field: `comparable_sales` (JSON)

**Impact:** 🔥🔥🔥 HIGH - Critical for ROI calculations

---

## Phase 2: Risk Intelligence (HIGH VALUE)

### 2.1 Location Analysis 🗺️
**Goal:** Understand the neighborhood

- [ ] **Distance to City Center**
  - Calculate miles to nearest major city
  - Flag if >30 miles (Capital Guardian deduction)
  - Database field: `distance_to_city_miles`, `nearest_city`

- [ ] **Road Access Type**
  - Paved, gravel, dirt, no access
  - Parse from assessor or infer from Street View
  - Database field: `road_access_type`

- [ ] **Flood Zone**
  - Query FEMA Flood Map API
  - Flag Zone A, AE, X (Capital Guardian kill switch)
  - Database field: `fema_flood_zone`, `is_flood_risk`

- [ ] **Environmental Hazards**
  - EPA Superfund site proximity
  - Wetlands designation
  - Database fields: `superfund_distance_miles`, `is_wetland`

**Impact:** 🔥🔥 MEDIUM-HIGH - Helps avoid problem properties

---

### 2.2 Market Context 📈
**Goal:** Buy in appreciating areas

- [ ] **County Market Trends**
  - Median sale price trend (up/down/flat)
  - Days on market average
  - Database fields: `median_price_trend`, `avg_days_on_market`

- [ ] **Population Growth**
  - County population trend (growing/declining)
  - Database field: `population_trend`

- [ ] **School District Rating**
  - If residential area, school quality matters
  - Database field: `school_rating` (1-10)

**Impact:** 🔥 MEDIUM - Helps prioritize counties/areas

---

## Phase 3: Tax Sale Calendar Integration

### 3.1 Auction Metadata 📅
**Goal:** Know when to bid, how to bid

- [ ] **Auction Date**
  - Extract from county tax sale calendar
  - Database field: `auction_date`

- [ ] **Auction Type**
  - Online, in-person, hybrid
  - Database field: `auction_type`

- [ ] **Registration Deadline**
  - When to register to bid
  - Database field: `registration_deadline`

- [ ] **Deposit Required**
  - How much upfront to bid
  - Database field: `deposit_amount`

- [ ] **Auction Platform**
  - URL to online bidding platform
  - Database field: `auction_platform_url`

**Impact:** 🔥🔥 MEDIUM-HIGH - Automates auction prep

---

## Phase 4: Portfolio Management

### 4.1 Bid Tracking 💼
**Goal:** Track what you bid on, what you won

- [ ] **Bid History Table**
  - Track: parcel, bid amount, result (won/lost)
  - Database table: `bids`

- [ ] **Watchlist**
  - Mark parcels to monitor
  - Database table: `watchlist`

- [ ] **Purchased Liens Table**
  - Track liens you own
  - Redemption status, interest accrued
  - Database table: `owned_liens`

**Impact:** 🔥🔥🔥 HIGH - Critical for managing a portfolio

---

## Phase 5: Automation & Alerts

### 5.1 Smart Notifications 🔔
**Goal:** Get alerted to opportunities

- [ ] **New BID Alerts**
  - Email/SMS when Capital Guardian says BID
  - Configurable thresholds (risk score > 70)

- [ ] **Price Drop Alerts**
  - If lien cost decreases (subsequent sales)
  - Database field: `price_history` (JSON)

- [ ] **Auction Reminders**
  - 7 days before, 1 day before

**Impact:** 🔥🔥 MEDIUM - Helps you act fast

---

## Phase 6: Advanced Analytics

### 6.1 ROI Calculator 📊
**Goal:** Project returns before bidding

- [ ] **Expected Return Calculator**
  - Input: lien cost, interest rate, redemption probability
  - Output: expected ROI, break-even analysis

- [ ] **Risk-Adjusted Returns**
  - Factor in Capital Guardian risk score
  - Show best risk/reward ratio

**Impact:** 🔥🔥 MEDIUM-HIGH - Helps prioritize bids

---

## Phase 7: Multi-County Expansion

### 7.1 More Scrapers 🌍
**Goal:** Scrape every county in Arizona, then USA

- [ ] Arizona Counties (14 remaining)
  - Navajo, Cochise, Yavapai, Pinal, Coconino, etc.

- [ ] High-ROI States
  - Texas (aggressive foreclosure)
  - Florida (high redemption rates)
  - Illinois (Cook County - huge volume)

**Impact:** 🔥🔥🔥 HIGH - More data = more opportunities

---

## Implementation Priority

### 🔴 Phase 1A - Quick Wins (THIS WEEK)
1. **Property Photos** - Google Street View URLs
2. **Lot Size & Zoning** - Scrape from assessor
3. **Assessed Value** - Already on assessor page
4. **Zillow/Realtor URLs** - Auto-generate from address

**Estimated Time:** 4-6 hours
**Impact:** Massive - gives you visual + valuation data immediately

---

### 🟡 Phase 1B - Medium Term (THIS MONTH)
5. **Flood Zone API** - FEMA integration
6. **Comparable Sales** - Zillow API or web scraping
7. **Legal Description Parsing** - Extract section/township/range
8. **Utilities Detection** - Parse assessor page

**Estimated Time:** 8-12 hours
**Impact:** High - better risk assessment

---

### 🟢 Phase 2+ - Long Term (NEXT MONTH)
9. **Auction Calendar Integration**
10. **Portfolio Management Tables**
11. **Email/SMS Alerts**
12. **Multi-County Scrapers**

**Estimated Time:** 20-40 hours
**Impact:** Transforms into full platform

---

## Database Schema Updates Needed

### New `scraped_parcels` columns:
```sql
-- Phase 1A (quick wins)
street_view_url VARCHAR(500)
lot_size_acres DECIMAL(10,2)
lot_size_sqft INT
zoning_code VARCHAR(50)
zoning_description VARCHAR(255)
assessed_land_value DECIMAL(12,2)
assessed_improvement_value DECIMAL(12,2)
assessed_total_value DECIMAL(12,2)
zillow_url VARCHAR(500)
realtor_url VARCHAR(500)
zillow_estimate DECIMAL(12,2)

-- Phase 1B (medium term)
legal_description TEXT
section VARCHAR(50)
township VARCHAR(50)
range_ VARCHAR(50)
has_water BOOLEAN DEFAULT 0
has_sewer BOOLEAN DEFAULT 0
has_electric BOOLEAN DEFAULT 0
land_use VARCHAR(100)
fema_flood_zone VARCHAR(10)
is_flood_risk BOOLEAN DEFAULT 0
aerial_image_url VARCHAR(500)

-- Phase 2 (long term)
auction_date DATE
auction_type VARCHAR(50)
distance_to_city_miles DECIMAL(6,2)
nearest_city VARCHAR(100)
road_access_type VARCHAR(50)
```

### New tables:
```sql
CREATE TABLE bids (
  id INT AUTO_INCREMENT PRIMARY KEY,
  parcel_id INT NOT NULL,
  bid_amount DECIMAL(12,2),
  bid_date DATETIME,
  result ENUM('pending','won','lost'),
  FOREIGN KEY (parcel_id) REFERENCES scraped_parcels(id)
);

CREATE TABLE watchlist (
  id INT AUTO_INCREMENT PRIMARY KEY,
  parcel_id INT NOT NULL,
  added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  notes TEXT,
  FOREIGN KEY (parcel_id) REFERENCES scraped_parcels(id)
);

CREATE TABLE owned_liens (
  id INT AUTO_INCREMENT PRIMARY KEY,
  parcel_id INT NOT NULL,
  purchase_price DECIMAL(12,2),
  purchase_date DATE,
  redemption_status ENUM('active','redeemed','foreclosed'),
  interest_accrued DECIMAL(12,2),
  FOREIGN KEY (parcel_id) REFERENCES scraped_parcels(id)
);
```

---

## 🚀 Let's Start!

**Want me to implement Phase 1A (Quick Wins) right now?**

I can add:
1. Google Street View URLs
2. Lot size extraction
3. Zoning extraction
4. Assessed value extraction
5. Zillow/Realtor URL generation

**This will take ~30 minutes and give you MASSIVE value immediately.**

Say the word and I'll make it happen! 🔥
