# Apache County Scraper - Lessons Learned & Gotchas

## Critical Issues Found & Fixed

### 1. ❌ Multiple Concurrent Scrapes (SOLVED)
**Problem**: Script could fire multiple times, causing 3+ concurrent scrape jobs fighting over same pages
**Solution**: Added lock mechanism
```bash
# Lock file: /tmp/lienhunter_Arizona_Apache.lock
# Checks: Script instance + Docker background job
# Result: Only ONE scrape can run at a time
```
**For Coconino**: Lock file will be `/tmp/lienhunter_Arizona_Coconino.lock` - automatic!

---

### 2. ⏱️ Timeout Too Short (SOLVED)
**Problem**: Original timeout was 5 minutes for a 3-6 hour scrape
**Symptoms**: Script would say "timeout" but scraper kept running in background
**Solution**: Replaced fixed timeout with smart progress checking
```bash
# Old: MAX_WAIT=300 (5 min, hard timeout)
# New: Check every 60 seconds, only fail if no progress for 5 min
# Result: Can run 24+ hours without timing out
```
**For Coconino**: Already have smart timeout built in!

---

### 3. 🔄 Page Detection Regex Issues (KNOWN)
**Problem**: Script's progress detection doesn't always find "Fetching page" in recent logs
**Symptoms**: Shows "no progress: 5/5" but scraper IS actually working
**Current Behavior**: Script thinks it failed, but scraper continues in background
**Impact**: Minor - we can verify scraper is actually running with direct Docker logs
```bash
docker logs tax_lien_v2-backend-1 2>&1 | grep "\[Apache\]" | tail -5
```
**For Coconino**: Same regex should work - just be aware it's imperfect
**Fix Available**: Could improve regex to capture log entries more reliably, but not critical

---

### 4. 📊 Data Extraction Patterns — REAL HTML STRUCTURE (verified 2026-02-17)

**CRITICAL**: The original regex patterns in apache.py were written WITHOUT seeing the real HTML.
All were broken. The following patterns are verified against actual fetched HTML.

---

#### 4a. Summary Page (`account.jsp?accountNum={pid}`)

**Owner Name** — Inline `<b>` tag (NOT a `<td>` row):
```html
<!-- Actual HTML -->
<b>Owner Name</b> 2 GUYS INVESTMENTS LLC
```
```python
# Working pattern
re.search(r'<b>Owner\s+Name</b>\s*([^\n<]+)', html)
```

**Owner Address** — Inline `<b>` with `<br>` between street and city/state/zip:
```html
<!-- Actual HTML -->
<b>Owner Address</b> PO BOX 265 <br>SNOWFLAKE, AZ 85937
```
```python
# Working pattern — captures through <br> tags
m = re.search(r'<b>Owner\s+Address</b>\s*((?:[^<]|<br[^>]*>)+)', html)
if m:
    addr = re.sub(r'<br[^>]*>', ' ', m.group(1)).strip()
```

**Situs Address** — Often EMPTY for vacant land:
```html
<!-- Actual HTML (vacant lot = empty) -->
<td><strong>Situs Address</strong> </td>
```
```python
# Pattern — must check length > 3 before using
m = re.search(r'<strong>Situs\s+Address</strong>\s*([^<]*)', html)
addr = m.group(1).strip() if m else None
if addr and len(addr) > 3:
    details["full_address"] = addr
```

**Legal Description** — After `</strong>` following "Legal Summary" heading with nested font tag:
```html
<!-- Actual HTML -->
<strong>Legal Summary <font color="red"> (Note: ...)</font></strong> Subdivision: CONCHO VALLEY UNIT 5 Block: 65 Lot: 1   Section: 19 Township: 12N Range: 26E
```
```python
# Working pattern — matches text after closing </strong>
re.search(r'Legal Summary[^<]*(?:<[^>]+>)*</strong>\s*([^<]+)', html)
```

**Full Cash Value (FCV)** — The label is `Full Cash Value (FCV)`, NOT "Total Value":
```html
<!-- Actual HTML - malformed table: <b> inline then <td> -->
<td align="left"><b>Full Cash Value (FCV)</b><td align="right">$5,900</td>
```
```python
# Working pattern — note escaped parentheses
re.search(r'Full Cash Value \(FCV\)</b><td[^>]*>\$?([\d,]+)', html)
```

**Legal Class** — In a malformed table row, `<td align="left">02.R</td>`:
```html
<th align="left" width="20%"><b>Legal Class</b></th>...
<tr><td align="left">02.R</td><td align="right">$5,900</td>...
```
```python
# Pattern (with DOTALL) — this one was already working
re.search(r'Legal Class.*?<td[^>]*>([^<]+)</td>', html, re.DOTALL | re.IGNORECASE)
```

**Parcel Detail Doc URL** — Sidebar nav link; needed for a second fetch to get lot size:
```html
<a class="null" href="account.jsp?accountNum=R0026183&doc=R0026183.1721088546772">Parcel Detail</a>
```
```python
# Extract the doc= parameter value
re.search(r'href="account\.jsp\?accountNum=[^&]+&doc=([^"]+)">Parcel Detail', html)
```

---

#### 4b. Parcel Detail Sub-Document (`account.jsp?accountNum={pid}&doc={pid}.{timestamp}`)

**Lot size requires a second HTTP request.** The lot size is NOT on the summary page.

URL pattern: `{ASSESSOR_URL}/account.jsp?accountNum={pid}&doc={doc_id}`

The doc ID is in the sidebar link (see pattern above).

**Parcel Size (Acreage)**:
```html
<span class="fieldLabel">Parcel Size</span><br/><span class="field"><span class="text">0.52&nbsp;</span></span>
```
```python
re.search(r'Parcel Size</span><br[^/]*/><span[^>]*><span[^>]*>([\d.]+)', html)
```

**Unit of Measure** (Acre / Sq Ft):
```html
<span class="fieldLabel">Unit of Measure</span><br/><span class="field"><span class="text">Acre&nbsp;</span></span>
```
```python
re.search(r'Unit of Measure</span><br[^/]*/><span[^>]*><span[^>]*>([^&<]+)', html)
```

---

#### 4c. What Is NOT Available on Apache Assessor

- **Coordinates** — Not in HTML text. Only accessible via GIS image embed or external GIS link.
- **Zoning** — Not on standard assessor page. Use parcel ID pattern to infer.
- **Improvement vs Land Value separately** — Summary page only shows Full Cash Value (FCV) total.
- **Improvement value** — Only on `AccountValue` sub-doc (assessment history).

---

#### ✅ Working (after fix):
- Parcel IDs from auction page
- Billed amounts from treasurer
- Owner name (inline `<b>` pattern)
- Owner mailing address (inline `<b>` with `<br>`)
- Full Cash Value (FCV) as assessed_total_value
- Legal description (after Legal Summary `</strong>`)
- Legal class (DOTALL table scan)
- Lot size in acres (requires second fetch to Parcel Detail sub-doc)

#### ⚠️ Missing (acceptable NULLs):
- Situs address for vacant land (page literally shows empty string)
- Coordinates (not in HTML)
- Zoning code (not on assessor pages)
- Improvement vs land value breakdown

---

### 5. 🌐 Website Structure Quirks

**Apache County uses "Eagle" software** for Assessor/Treasurer:
- URL: `https://eagleassessor.co.apache.az.us/assessor/taxweb`
- Requires guest login to access account pages
- Uses POST request with `data={"submit": "Login", "guest": "true"}`
- Cookies must be maintained for subsequent requests

**For Coconino**: Check if they also use "Eagle" - if yes, authentication pattern is same!

---

### 6. 🔑 Authentication & Sessions

**Current Implementation**:
```python
async def _login_assessor(self):
    response = await self.session.post(
        f"{self.ASSESSOR_URL}/loginPOST.jsp",
        data={"submit": "Login", "guest": "true"},
        headers=headers,
        follow_redirects=True,
    )
    self.assessor_cookies = response.cookies
```

**Gotcha**: Session might expire after ~1 hour
**Solution**: Call login methods fresh for each parcel? (Currently done, but slow)
**For Coconino**: Verify if Coconino needs re-login or if session persists longer

---

### 7. ⏳ Rate Limiting & Delays

**Current Delays**:
- Per parcel request: 2-8 seconds (random)
- Per page navigation: 10-30 seconds (random)

**Effective Rate**: ~2-3 parcels per minute

**Gotcha**: If delays are too short, website might:
- Block requests (403 Forbidden)
- Return empty pages
- Rate limit responses

**For Coconino**: Start with same delays. If getting blocked, increase to 3-10s per parcel

---

### 8. 💾 Database Issues Fixed

**Added Columns**:
```sql
ALTER TABLE scraped_parcels
ADD COLUMN owner_name VARCHAR(255) NULL,
ADD COLUMN owner_mailing_address TEXT NULL;
```

**Insertion Pattern**:
```python
text("""INSERT IGNORE INTO scraped_parcels
    (...parcel_id, owner_name, owner_mailing_address, ...)
    VALUES (...:parcel_id, :owner_name, :owner_mailing_address, ...)""")
```

**For Coconino**: Database is ready - just add owner extraction to scraper

---

### 9. 🎯 Data Quality Notes

**Owner Name Issues**:
- May include "AND" for multiple owners (e.g., "SMITH JOHN AND JANE")
- May include middle initials or business names
- Cleaning: Trim whitespace, remove extra spaces

**Assessed Values Issues**:
- Sometimes shown as ranges or estimates ("~$150,000")
- Parse float, not strings with commas: `float(value.replace(",", ""))`
- Some parcels have $0 assessed value (vacant/exempt land)

**Coordinates Issues**:
- Format varies: sometimes decimal, sometimes DMS (degrees/minutes/seconds)
- May be on map embed, not in HTML text
- Must validate: Arizona bounds are roughly 31-37°N, 109-115°W

---

### 10. 🧪 Testing Recommendations

**Before Full Scrape of Coconino**:
1. Test with `limit=5` first (takes ~30-60 seconds)
2. Verify all 20+ fields are populated or NULL (not missing)
3. Check owner extraction specifically works
4. Spot-check coordinates are in Arizona range
5. Look for any HTML parsing errors in logs

**Example Test**:
```bash
./run_scrape_assess.sh Arizona Coconino 5 100
```

---

### 11. 📝 Logging Best Practices

**Current Good Practices**:
```python
print(f"[Apache] Fetching page {page}...", flush=True)
print(f"[Apache] {pid}: ${billed:.2f}, {acres}ac, Value=${value}, Zone={zoning}", flush=True)
print(f"[Apache] Scraped {len(liens)} total", flush=True)
```

**For Coconino**: Use `[Coconino]` prefix to distinguish logs
- Helps when monitoring multiple counties
- Makes grep easier: `docker logs | grep "\[Coconino\]"`

---

## Summary: What to Do Different for Coconino

✅ **Keep Same**:
- Lock mechanism (automatic)
- Smart timeout (automatic)
- Rate limiting delays (2-8s, 10-30s)
- Owner extraction patterns
- Database INSERT pattern

⚠️ **Verify Early**:
- Authentication method (is it "Eagle"?)
- Pagination structure (how many pages?)
- Data field mappings (may differ from Apache)
- Coordinates availability
- Owner name/address presence

🔧 **Potential Optimizations**:
- Could optimize page detection regex
- Could cache authentication longer
- Could parallelize parcel fetching (careful with rate limits!)

---

## File Reference

**Apache County Scraper**: `backend/app/scrapers/arizona/apache.py`
**Key Methods**:
- `scrape(limit)` - Main loop
- `_get_auction_page(page_num)` - Fetch page
- `_get_total_billed(pid)` - Get tax amount
- `_get_parcel_details(pid)` - Extract owner, coords, values
- `_login_assessor()` - Authentication
- `_build_*_url()` - Generate mapping URLs

**Patterns to Copy**: The URL building methods are reusable!

---

---

## Lessons Learned 2026-02-17 (Session 2)

### 12. 🗺️ GIS / Coordinates — ArcGIS REST API (FREE, no auth)

Apache County publishes its parcel polygon layer as a public ArcGIS hosted service.

**Service URL:**
```
https://services8.arcgis.com/KyZIQDOsXnGaTxj2/arcgis/rest/services/Parcels/FeatureServer/0/query
```

**Query by account number to get centroid + situs:**
```
?where=ACCOUNTNUMBER='R0026183'
&outFields=ACCOUNTNUMBER,PARCEL_NUM,OWNERNAME,SITUS
&returnGeometry=true
&returnCentroid=true
&outSR=4326
&f=json
```

**Key fields returned:**
| Field | Value |
|---|---|
| `ACCOUNTNUMBER` | R0026183 (same as assessor account) |
| `PARCEL_NUM` | 201-31-065A (the formatted APN) |
| `SITUS` | Street address IF one exists |
| `centroid.y` / `centroid.x` | Lat / Lon in WGS84 |

**Gotcha: SITUS is blank for vacant lots.** Use ESRI reverse geocode instead (see #13).

**Implemented in:** `ApacheScraper._get_gis_data()`

---

### 13. 📍 Street Addresses — ESRI Reverse Geocoder (FREE, no auth)

Nominatim (OSM) returns only "Apache County, Arizona" for remote rural parcels.
ESRI World Geocoder knows rural county roads and returns real results.

**API:**
```
GET https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/reverseGeocode
  ?location={lon},{lat}
  &f=json
```

**Returns** `address.Match_addr` — e.g. `"41 County Road 8105, Concho, Arizona, 85924"`

**Important caveat:** For vacant lots, ESRI returns the nearest *addressed property* on the
same road, not the lot's own assigned address (vacant lots have no assigned number).
Two adjacent lots may get the same "nearest address." The Maps link (lat/lon) is always
more precise than the address string for navigation.

**Special cases observed:**
- `"Petrified Forest National Park"` → parcel is inside/adjacent to federal land — RED FLAG
- `"85936, Saint Johns, Arizona"` → ZIP only, no road data in that area
- `"27 County Road N3315, Concho, AZ 85924"` → confirms assessor situs "27 N3315" was correct

**Implemented in:** `ApacheScraper._get_gis_data()` (called automatically when SITUS is empty)

---

### 14. 🏦 Treasurer Page — `&action=tx`

URL pattern: `https://eagletreasurer.co.apache.az.us:8443/treasurer/treasurerweb/account.jsp?account={pid}&action=tx`

**What it shows:**
- Full tax payment history by year
- Each year's billed amount, paid amount, balance
- Whether owner has been consistently delinquent (multiple years back)
- Prior tax sales on this parcel
- Interest accrued

**Why it matters for investing:**
- Multiple years delinquent = higher total redemption cost (risky)
- Owner who paid every year until recently = more likely to redeem (good)
- Prior tax sales = land has a history of abandonment (risky or opportunity)

**Currently:** We only scrape `Total Billed` from the treasurer. The `&action=tx` endpoint
has richer data but requires parsing the full transaction table.

---

### 15. 🔄 Assessment Job — Known Issues & Fixes

**Problem: Jobs get stuck in `assessing` state**
- Cause: `llama3.1:70b` cold-start on DGX Spark takes 2-3 min; combined with httpx 180s
  timeout = occasional job hangs that never timeout
- Symptom: `assess.sh` reports "no progress: 10/10" and exits, but rows stuck in DB
- Fix: `UPDATE assessments SET assessment_status='pending' WHERE assessment_status='assessing';`
- Then: `docker compose restart backend` to kill the stuck thread
- Prevention: Run smaller batches (20-50 parcels) rather than 200 at a time

**Problem: Multiple concurrent jobs from repeated `./assess.sh` runs**
- Each run starts a NEW job even if one is already running
- Fix: Check `SELECT COUNT(*) FROM assessments WHERE assessment_status='assessing'` before running
- If > 0, either wait or reset and restart

**Assessment pipeline confirmed working:**
1. Python Gate 1 kills switch logic → DO_NOT_BID with no LLM call (fast)
2. LLM Gate 4 scoring → BID or DO_NOT_BID with risk_score + max_bid
3. Results written to `assessments` table immediately per parcel
4. 157 parcels successfully assessed as of 2026-02-17

---

**Last Updated**: 2026-02-17
**Status**: Apache scrape complete (~9,750 parcels). Assessment in progress (157/~2,000 assessed). 14 BID parcels have full data including coordinates and addresses.
