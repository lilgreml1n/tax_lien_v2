# BUILD: Coconino County Tax Lien Scraper

## Quick Reference (Read This First)

**Deadline**: As soon as possible
**Scope**: Build complete Coconino County scraper (mirror Apache structure)
**Reference**: Apache County scraper already exists at `backend/app/scrapers/arizona/apache.py`
**Gotchas**: See `APACHE_COUNTY_GOTCHAS.md` for lessons learned
**Database**: Already has `owner_name` and `owner_mailing_address` columns

---

## Phase 1: RESEARCH (You Do This First)

Before building, answer these questions:

### A. Find Coconino County URLs

1. **Auction/Lien Listings**
   - Visit: Coconino County tax sale website
   - Find: URL for listing all parcels in current auction
   - Document: URL pattern (usually has pagination like `?pageNum=1`)
   - Question: How many pages total?

2. **Treasurer System**
   - Find: Tax payment/bill lookup by parcel ID
   - Document: Full URL pattern with parcel ID parameter
   - Test: Try a known parcel ID to verify access
   - Question: Is it same "Eagle" system as Apache?

3. **Assessor System**
   - Find: Property details lookup by parcel ID
   - Document: Full URL pattern with parcel ID parameter
   - Test: Try same parcel ID, verify you can access it
   - Question: Is it same "Eagle" system?

### B. Authentication Check

1. Does Coconino use guest login or open access?
2. If login required: What are the credentials/method?
3. Does session persist or need re-login for each request?
4. Document any differences from Apache

### C. Data Availability Check

Test with ONE parcel ID. Verify these fields exist on the pages:
- [ ] Owner name
- [ ] Owner mailing address
- [ ] Lot size in acres
- [ ] Assessed values (land/improvement/total)
- [ ] Latitude/longitude
- [ ] Zoning code
- [ ] Legal description
- [ ] Parcel ID format (similar to Apache's R0025877?)

### D. Page Structure Check

1. View source of a listing page - what format are parcel IDs in?
2. View source of an assessor page - where is owner name located?
3. View source of treasurer page - where is tax amount?
4. Note any HTML differences from Apache

---

## Phase 2: BUILD (I Do This)

Once you provide research above, I will:

### Step 1: Create Scraper File
Create: `backend/app/scrapers/arizona/coconino.py`

Structure (same as Apache):
```python
class CoconinoScraper(CountyScraper):
    AUCTION_URL = "..."
    TREASURER_URL = "..."
    ASSESSOR_URL = "..."

    async def scrape(self, limit: int = 0) -> List[Dict]:
        # Main loop: pages -> parcel IDs -> fetch details
        # Returns list of dicts with all required fields
```

### Step 2: Implement Required Methods
- `_get_auction_page(page_num)` - Extract parcel IDs from listing
- `_get_total_billed(pid)` - Get tax amount from treasurer
- `_get_parcel_details(pid)` - Get owner, coords, values from assessor
- `_login_*()` - Authentication (if needed)
- `_build_*_url()` - Copy from Apache (reusable)

### Step 3: Extract All Required Fields

**MUST EXTRACT** (required):
- `parcel_id` - Unique identifier
- `owner_name` - Current owner (use patterns from Apache)
- `owner_mailing_address` - Tax bill address
- `billed_amount` - Total tax owed (float)
- `legal_class` - Property type
- `full_address` - Physical location

**SHOULD EXTRACT** (if available):
- `latitude`, `longitude` - For mapping
- `lot_size_acres`, `lot_size_sqft` - Property size
- `zoning_code`, `zoning_description` - Zoning info
- `assessed_land_value`, `assessed_improvement_value`, `assessed_total_value` - Values
- `legal_description` - Legal property description

**Generated URLs**:
- `google_maps_url`, `street_view_url`, `assessor_url`, `treasurer_url`
- `zillow_url`, `realtor_url` (use existing `_build_*` methods from Apache)

### Step 4: Add Proper Delays

```python
# For EACH parcel request
await HumanBehavior.request_delay()  # 2-8 seconds

# For EACH page navigation
await HumanBehavior.page_delay()  # 10-30 seconds
```

### Step 5: Add Logging

```python
print(f"[Coconino] Fetching page {page}...", flush=True)
print(f"[Coconino] {pid}: ${billed:.2f}, {acres}ac, Value=${value}", flush=True)
print(f"[Coconino] Scraped {len(liens)} total", flush=True)
```

### Step 6: Return Proper Format

Each parcel dict must have:
```python
{
    "parcel_id": "...",
    "state": "Arizona",
    "county": "Coconino",
    "billed_amount": 123.45,
    "owner_name": "...",
    "owner_mailing_address": "...",
    "legal_class": "...",
    "full_address": "...",
    "latitude": 35.1234,
    "longitude": -111.5678,
    # ... all other fields
    "google_maps_url": "...",
    "assessor_url": "...",
    # ... etc
}
```

---

## Phase 3: REGISTER (You Do This)

After scraper is built, register it:

```bash
curl -X POST http://localhost:8001/scrapers/config \
  -H "Content-Type: application/json" \
  -d '{
    "state": "Arizona",
    "county": "Coconino",
    "scraper_name": "app.scrapers.arizona.coconino.CoconinoScraper",
    "scraper_version": "1.0"
  }'
```

Update registry in `backend/app/routers/scrapers.py`:
```python
SCRAPER_REGISTRY = {
    "app.scrapers.arizona.apache.ApacheScraper": None,
    "app.scrapers.arizona.coconino.CoconinoScraper": None,  # ADD THIS
}
```

---

## Phase 4: TEST (You Do This)

Test with small limit first:

```bash
./run_scrape_assess.sh Arizona Coconino 5 100
```

**Check**:
- [ ] Completes without errors
- [ ] All 20+ fields present (or NULL if data missing)
- [ ] Owner name is populated
- [ ] Owner mailing address is populated
- [ ] Billed amount is correct
- [ ] Took ~30-60 seconds (rate limiting working)

**Sample Output Should Show**:
```
[Coconino] Fetching page 1...
[Coconino] R0025877: $123.45, 0.5ac, Value=$200000, Zone=R-1
[Coconino] R0025878: $456.78, 1.2ac, Value=$350000, Zone=C-1
...
[Coconino] Scraped 5 total
```

---

## Phase 5: FULL SCRAPE (You Do This)

Once test passes:

```bash
./scrape_all_coconino.sh
```

This will:
1. Check for conflicts (lock mechanism)
2. Scrape all pages (~3-6 hours)
3. Extract owner data
4. Save to database
5. Report results

---

## Important Notes

### ✅ What's Automatic

- Lock mechanism prevents multiple runs
- Smart timeout (checks every 60s, fails only after 5 min inactivity)
- Database INSERT statement (already set up for owner fields)
- URL building helpers (copied from Apache)
- Rate limiting (use HumanBehavior delays)

### ⚠️ What Can Go Wrong

1. **Authentication different** - May need custom login if not "Eagle" system
2. **HTML very different** - May need custom regex patterns
3. **Missing fields** - Coconino may not have certain data Apache has
4. **Rate limiting** - If you get 403/429 responses, increase delays
5. **Coordinates unavailable** - Some counties don't publish lat/lon

### 🔧 If Stuck

Check `APACHE_COUNTY_GOTCHAS.md` for:
- Common HTML parsing issues
- Data quality problems
- Authentication troubleshooting
- Rate limiting solutions

---

## Comparison: Apache vs Coconino Template

| Aspect | Apache | Coconino |
|--------|--------|----------|
| URLs | Documented ✅ | Research Needed 🔍 |
| Auth | Eagle (guest) ✅ | TBD 🔍 |
| Data Fields | 20+ extracted ✅ | Same expected ✅ |
| Owner Extract | Added ✅ | Same method ✅ |
| Database | Ready ✅ | Ready ✅ |
| Delays | 2-8s, 10-30s ✅ | Same ✅ |
| Lock/Timeout | Built ✅ | Same ✅ |

---

## Timeline Estimate

- **Phase 1 (Research)**: 30-45 min
- **Phase 2 (Build)**: 1-2 hours (once research done)
- **Phase 3 (Register)**: 5 min
- **Phase 4 (Test)**: 2-3 min
- **Phase 5 (Full Scrape)**: 3-6 hours (runs in background)

**Total**: ~2-4 hours active work + 3-6 hours passive scraping

---

## Success Criteria

✅ **Complete when**:
- [ ] Scraper file created and registered
- [ ] Test scrape of 5 parcels works
- [ ] All required fields populated or NULL
- [ ] Full county scrape completes (1,000+ parcels)
- [ ] Owner data successfully captured
- [ ] No errors in logs during full scrape

---

## Questions Before We Start?

Ready for Phase 1: Research?

Please provide:
1. Coconino County auction URL
2. Treasurer lookup URL pattern
3. Assessor lookup URL pattern
4. Authentication method (if any)
5. Estimated total parcels/pages
6. Confirmation that owner data exists

Then I can build the complete scraper in one shot!

---

**Reference Files**:
- Apache Scraper: `backend/app/scrapers/arizona/apache.py`
- Gotchas: `APACHE_COUNTY_GOTCHAS.md`
- Prompt Template: `COCONINO_SCRAPER_PROMPT.md`
