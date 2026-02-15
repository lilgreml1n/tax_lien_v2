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

### 4. 📊 Data Extraction Patterns

#### ✅ Working Well:
- Parcel IDs from auction page
- Billed amounts from treasurer
- Assessed values (land, improvement, total)
- Lot size in acres
- Zoning codes

#### ⚠️ Often Missing/Null:
- **Owner Name** - Not always present in scraped data (add extraction logic)
- **Owner Mailing Address** - Not always present (add extraction logic)
- **Latitude/Longitude** - Sometimes missing (coordinates not on all pages)
- **Zoning Description** - Often defaults to "See County Zoning"
- **Property Type** - May need custom mapping per county

#### ❌ Hard to Extract (low success rate):
- Legal descriptions (very inconsistent HTML)
- Coordinates (not always on page, various formats)
- Improvement vs Land value breakdown (sometimes combined)

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

**Last Updated**: 2026-02-15
**Status**: Apache scrape in progress (Job: scrape_Arizona_Apache_1771160250)
