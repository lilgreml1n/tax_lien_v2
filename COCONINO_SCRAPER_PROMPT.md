# Coconino County Tax Lien Scraper - Build Prompt

## Project Context
This is for the LienHunter v2 system that scrapes Arizona county tax lien auction data. We already have Apache County working. Now building Coconino County scraper.

## Technical Requirements

### 1. Scraper Architecture
- **Base Class**: Inherit from `CountyScraper` in `app/scrapers/base.py`
- **File Location**: `backend/app/scrapers/arizona/coconino.py`
- **Class Name**: `CoconinoScraper`
- **Pattern**: Follow the same structure as `apache.py`

### 2. Required Data Sources (URLs to investigate)
Coconino County typically uses these systems:
- **Auction Listings**: Find the tax lien auction/sale website
- **Treasurer**: Tax/payment records (billed amounts, payment history)
- **Assessor**: Property details (owner, legal class, values, coordinates)

**ACTION NEEDED**: Research and provide:
1. Auction listing URL
2. Treasurer lookup URL (by parcel ID)
3. Assessor lookup URL (by parcel ID)
4. Authentication requirements (guest login, cookies, sessions, etc.)

### 3. Data Points to Extract (MANDATORY)

#### From Auction Listing:
- `parcel_id` - Unique parcel identifier (REQUIRED)

#### From Treasurer:
- `billed_amount` - Total tax amount owed (REQUIRED, FLOAT)

#### From Assessor:
- `owner_name` - Current property owner (REQUIRED, VARCHAR 255)
- `owner_mailing_address` - Tax bill mailing address (REQUIRED, TEXT)
- `legal_class` - Property classification (e.g., "Vacant Land", "Single Family")
- `full_address` - Physical property address (situs address)
- `latitude` - GPS coordinate (FLOAT, for mapping)
- `longitude` - GPS coordinate (FLOAT, for mapping)
- `lot_size_acres` - Property size in acres (FLOAT)
- `lot_size_sqft` - Property size in square feet (INT)
- `zoning_code` - Zoning designation (e.g., "R-1", "C-1")
- `zoning_description` - Zoning description
- `assessed_land_value` - Land value assessment (FLOAT)
- `assessed_improvement_value` - Building/improvement value (FLOAT)
- `assessed_total_value` - Total assessed value (FLOAT)
- `legal_description` - Legal property description (TEXT, max 1000 chars)

### 4. URL Generation (Auto-generated, include in output)
For each parcel, generate these URLs:
- `google_maps_url` - Use `_build_google_maps_url()` helper
- `street_view_url` - Use `_build_street_view_url()` helper
- `assessor_url` - Direct link to assessor record
- `treasurer_url` - Direct link to treasurer record
- `zillow_url` - Use `_build_zillow_url()` helper
- `realtor_url` - Use `_build_realtor_url()` helper

### 5. Rate Limiting & Human Behavior (CRITICAL)
Use `HumanBehavior` class for delays:
- `await HumanBehavior.request_delay()` - 2-8 seconds between parcel requests
- `await HumanBehavior.page_delay()` - 10-30 seconds between page requests
- `HumanBehavior.get_headers()` - Randomized user agents

**Why**: Avoid detection and rate limiting. These delays are intentional!

### 6. Scraper Method Signature
```python
async def scrape(self, limit: int = 0) -> List[Dict[str, Any]]:
    """
    Scrape Coconino County tax lien parcels.

    Args:
        limit: Max parcels to scrape (0 = all parcels)

    Returns:
        List of lien dictionaries with all required fields
    """
```

### 7. Expected Output Format
Each parcel dictionary must contain:
```python
{
    "parcel_id": "123-45-678",
    "state": "Arizona",
    "county": "Coconino",
    "billed_amount": 1234.56,
    "owner_name": "SMITH JOHN & JANE",
    "owner_mailing_address": "123 Main St, Flagstaff AZ 86001",
    "legal_class": "Single Family Residence",
    "full_address": "456 Oak Ave, Flagstaff, AZ 86001",
    "latitude": 35.1983,
    "longitude": -111.6513,
    "lot_size_acres": 0.25,
    "lot_size_sqft": 10890,
    "zoning_code": "R-1",
    "zoning_description": "Single Family Residential",
    "assessed_land_value": 50000.00,
    "assessed_improvement_value": 150000.00,
    "assessed_total_value": 200000.00,
    "legal_description": "LOT 5 BLK 3 MOUNTAIN VIEW SUBDIVISION...",
    "google_maps_url": "https://www.google.com/maps/search/?api=1&query=35.1983,-111.6513",
    "street_view_url": "https://www.google.com/maps/@35.1983,-111.6513,3a,75y,0h,90t/...",
    "assessor_url": "https://...",
    "treasurer_url": "https://...",
    "zillow_url": "https://...",
    "realtor_url": "https://..."
}
```

### 8. Regex Patterns & Parsing
**Common patterns to use** (adapt based on actual HTML):

```python
# Owner Name
r"(?:Owner|Taxpayer)\s*Name[:\s]+([^<\n]{2,200})"

# Mailing Address
r"(?:Mailing|Tax)\s+Address[:\s]+([^<\n]{5,500})"

# Legal Class
r"Legal Class.*?<td[^>]*>([^<]+)</td>"

# Coordinates
r"latitude[\"']?\s*[:=]\s*([0-9.-]+)"
r"longitude[\"']?\s*[:=]\s*([0-9.-]+)"

# Lot Size
r"([0-9.]+)\s*(?:acres?|ac)"

# Assessed Values
r"Total\s+(?:Assessed\s+)?Value[:\s]+\$?\s*([\d,]+)"
```

### 9. Error Handling & Logging
```python
# Log progress clearly
print(f"[Coconino] Fetching page {page}...", flush=True)
print(f"[Coconino] {pid}: ${billed:.2f}, {acres}ac, Value=${value}", flush=True)

# Handle missing data gracefully
billed_amount = billed_amount or 0.0
owner_name = owner_name or "Unknown"
```

### 10. Testing Requirements
Before full scrape, test with:
```python
# Test with limit
scraper = CoconinoScraper("Arizona", "Coconino")
liens = await scraper.scrape(limit=5)
print(f"Scraped {len(liens)} parcels")
print(f"Sample: {liens[0]}")
```

**Verify**:
- All required fields are present
- No crashes on missing data
- Delays are working (should take ~30-60 seconds for 5 parcels)
- Owner names are extracted correctly
- Coordinates are valid Arizona lat/lon

### 11. Registration
After building scraper, register it:
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

### 12. Scraper Registry
Add to `backend/app/routers/scrapers.py`:
```python
SCRAPER_REGISTRY = {
    "app.scrapers.arizona.apache.ApacheScraper": None,
    "app.scrapers.arizona.coconino.CoconinoScraper": None,  # ADD THIS
}
```

---

## What I Need From You (Claude)

### Step 1: Research Phase
1. Find Coconino County auction listing URL
2. Find Treasurer and Assessor URLs
3. Document authentication requirements (guest login? cookies?)
4. Identify pagination method (if any)
5. Estimate total parcels available

### Step 2: Build Phase
1. Create `backend/app/scrapers/arizona/coconino.py`
2. Implement all required data extraction methods
3. Include proper error handling and logging
4. Follow Apache County structure as reference

### Step 3: Test Phase
1. Test with limit=5 first
2. Verify all required fields are present
3. Check data quality (valid coordinates, owner names, etc.)

### Step 4: Deliver
Provide:
- Complete `coconino.py` file
- Registration command
- Sample output from test scrape
- Any quirks or special notes about this county

---

## Common Gotchas to Avoid

❌ **Don't**:
- Skip owner extraction (we need this!)
- Forget rate limiting delays
- Hard-code URLs without parameters
- Ignore missing data (use defaults)
- Cache sessions without closing them

✅ **Do**:
- Use `INSERT IGNORE` pattern (already handled by backend)
- Log progress clearly with `flush=True`
- Handle missing/malformed data gracefully
- Test with small limit first
- Close httpx sessions in finally block

---

## Expected Timeline
Based on Apache County experience:
- Research: 30-45 minutes
- Build: 1-2 hours
- Test & debug: 30-60 minutes
- **Total: 2-4 hours**

---

## Questions to Answer During Research
1. Does Coconino use the same "Eagle" software as Apache?
2. Is guest authentication required?
3. How many pages of auction listings exist?
4. Are coordinates available on assessor pages?
5. Is legal class labeled differently? (e.g., "Property Type" vs "Legal Class")

---

Ready to start! Please begin with **Step 1: Research Phase** and document your findings.
