# County Scraper Specification & Playbook

## Why Apache Works

Apache County scraper succeeds because of three well-structured sources that work together:

```
Auction Site  →  Parcel IDs (paginated list)
Treasurer     →  Billed Amount (what you owe to win the lien)
Assessor      →  Everything else (value, owner, zoning, legal class, GPS, address)
```

Each source requires a **guest login** first (POST to loginPOST.jsp), then
cookies are reused for all subsequent requests. Human-like delays run between
each parcel request (2-8s) and between pages (10-30s).

### What Apache Returns Per Parcel
```
parcel_id             R0106010
billed_amount         $3,254.98    ← from Treasurer
legal_class           Unknown/4A/etc ← from Assessor
full_address          123 Main St    ← from Assessor
latitude / longitude  34.12 / -110.3 ← from Assessor (embedded JS)
lot_size_acres        1.5            ← from Assessor
assessed_total_value  $45,000        ← from Assessor
zoning_code           RU             ← from Assessor
legal_description     LOT 12 BLK 3   ← from Assessor
owner_name            JOHN DOE       ← from Assessor
owner_mailing_address 123 Oak St     ← from Assessor
assessor_url          (clickable)
treasurer_url         (clickable)
google_maps_url       (clickable)
street_view_url       (clickable)
zillow_url            (clickable)
realtor_url           (clickable)
```

---

## The Required Data Contract

Every scraper MUST return this dict per parcel (NULLs allowed where not available):

```python
{
    # Identity
    "parcel_id":                str,    # REQUIRED - unique ID
    "state":                    str,    # REQUIRED - e.g. "Arizona"
    "county":                   str,    # REQUIRED - e.g. "Apache"
    "address":                  str,    # REQUIRED - fallback "County, State"

    # Money
    "billed_amount":            float,  # NULL OK - the lien amount (what you pay)

    # Property details
    "legal_class":              str,    # NULL OK - tax classification code
    "full_address":             str,    # NULL OK - physical property address
    "latitude":                 float,  # NULL OK - GPS
    "longitude":                float,  # NULL OK - GPS
    "lot_size_acres":           float,  # NULL OK
    "lot_size_sqft":            int,    # NULL OK
    "zoning_code":              str,    # NULL OK - e.g. "R-1"
    "zoning_description":       str,    # NULL OK - e.g. "Single Family Residential"
    "assessed_land_value":      float,  # NULL OK
    "assessed_improvement_value": float, # NULL OK
    "assessed_total_value":     float,  # NULL OK
    "legal_description":        str,    # NULL OK

    # Owner
    "owner_name":               str,    # NULL OK
    "owner_mailing_address":    str,    # NULL OK

    # Review Links (always populate what you can)
    "assessor_url":             str,    # NULL OK
    "treasurer_url":            str,    # NULL OK
    "google_maps_url":          str,    # NULL OK
    "street_view_url":          str,    # NULL OK
    "zillow_url":               str,    # NULL OK
    "realtor_url":              str,    # NULL OK
}
```

---

## Problems With Current Code (Things To Fix)

### 1. URL Builders Are Duplicated
`_build_google_maps_url`, `_build_street_view_url`, `_build_zillow_url`,
`_build_realtor_url` are copy-pasted identically in both `apache.py` and
`coconino.py`. They belong in `base.py` on `CountyScraper` so every new
scraper gets them for free.

### 2. Assessor Regex Patterns Are Duplicated
The regex patterns for legal class, address, GPS, lot size, zoning, values,
legal description, and owner are copy-pasted in both scrapers. These should
move to a shared helper in `base.py`:
```python
def _parse_assessor_html(self, html: str) -> dict:
    """Standard assessor page parser - works for Eagle/TaxWeb systems"""
```

### 3. Coconino `_get_parcel_details` Is Empty
It returns all NULLs. The assessor integration is stubbed. The regex patterns
already exist in `_parse_base_document` - that method just needs to be called.

### 4. Individual Parcel Failures Were Silent
Fixed in Apache. Apply same try/except pattern to Coconino.

---

## Refactored Base Class (Target State)

Move shared logic into `base.py` so scrapers only implement what's unique:

```python
class CountyScraper(ABC):

    # Override in each scraper
    COUNTY_NAME = ""

    # ── Shared: URL builders ──────────────────────────────────────────────
    def _build_google_maps_url(self, lat, lon, address, parcel_id): ...
    def _build_street_view_url(self, lat, lon, address): ...
    def _build_zillow_url(self, address, parcel_id): ...
    def _build_realtor_url(self, address, parcel_id): ...

    # ── Shared: Standard Eagle/TaxWeb assessor parser ─────────────────────
    def _parse_assessor_html(self, html: str) -> dict:
        """Parses standard Eagle/TaxWeb assessor pages used by many AZ counties"""
        # Legal class, address, GPS, lot size, zoning, values, description, owner

    # ── Shared: Guest login helper ────────────────────────────────────────
    async def _guest_login(self, base_url: str) -> dict:
        """POST loginPOST.jsp with guest=true, return cookies"""

    # ── Each scraper implements these ─────────────────────────────────────
    @abstractmethod
    async def scrape(self, limit, start_page, on_page_complete): ...

    @abstractmethod
    async def _get_auction_page(self, page_num) -> list: ...

    # Optional - not every county has a separate treasurer
    async def _get_billed_amount(self, pid: str) -> float: ...
```

---

## Playbook: Adding a New County

### Step 1: Research (30-60 min)

Find these 3 URLs for the new county:

**A. Auction page** - where the tax sale listings are
- Usually at `{county}.arizonataxsale.com` for Arizona
- Look for: paginated table of parcels with Parcel ID + Face Amount (bid price)
- Check: what's the pagination mechanism? (page= param, POST form, JS?)

**B. Assessor** - property data lookup
- Search for `{county} county assessor parcel search`
- Many Arizona counties use Eagle/TaxWeb: `eagleassessor.co.{county}.az.us`
- Test with a known parcel ID from the auction page
- Check: does it require login? (try guest/guest or no login)

**C. Treasurer** - how much is owed
- May be combined with assessor site, or separate
- Many Arizona counties use Eagle: `eagletreasurer.co.{county}.az.us`
- Look for a "Total Billed" field on the account page
- Check: does it require login? (try guest/guest)

### Step 2: Verify Sources With curl

```bash
# Test auction page
curl -s "https://{county}.arizonataxsale.com/index.cfm?folder=previewitems" | grep -c "parcel"

# Test assessor (replace R0012345 with a real parcel ID from auction)
curl -sk "https://eagleassessor.co.{county}.az.us/assessor/taxweb/account.jsp?accountNum=R0012345" | grep -i "legal class"

# Test treasurer
curl -sk "https://eagletreasurer.co.{county}.az.us:8443/treasurer/treasurerweb/account.jsp?account=R0012345" | grep -i "total billed"
```

### Step 3: Note The Differences From Apache

| Feature | Apache | New County |
|---------|--------|------------|
| Auction pagination | POST pageNum= | ? |
| Parcel ID format | R + 7 digits | ? |
| Requires login | Yes (guest) | ? |
| Face Amount on auction | No (get from treasurer) | ? |
| Assessor URL format | accountNum= | ? |
| Treasurer exists | Yes | ? |

### Step 4: Create The Scraper File

```
backend/app/scrapers/{state_lower}/{county_lower}.py
```

Template structure:

```python
"""
{County} County, {State} Scraper

Sources:
- Auction: {auction_url}
- Treasurer: {treasurer_url} (or NULL if not available)
- Assessor: {assessor_url}

Notes:
- Parcel ID format: {format}
- Pagination: {method}
- Face Amount: {where it comes from}
"""
import re
import httpx
from typing import List, Dict, Any, Callable, Optional
from app.scrapers.base import CountyScraper, HumanBehavior


class {County}Scraper(CountyScraper):

    AUCTION_URL = "{auction_url}"
    TREASURER_URL = "{treasurer_url}"   # or remove if not available
    ASSESSOR_URL = "{assessor_url}"

    def __init__(self, state: str, county: str):
        super().__init__(state, county)
        self.treasurer_cookies = None
        self.assessor_cookies = None

    async def scrape(self, limit: int = 0, start_page: int = 1,
                     on_page_complete: Optional[Callable] = None):
        liens = []
        total_scraped = 0
        try:
            await self._login_treasurer()   # remove if no treasurer
            await self._login_assessor()

            page = start_page
            max_pages = 500  # Will stop when no parcels found

            if start_page > 1:
                print(f"[{county}] Resuming from page {start_page}", flush=True)

            while page <= max_pages:
                print(f"[{county}] Fetching page {page}...", flush=True)

                parcel_data = await self._get_auction_page(page)
                if not parcel_data:
                    print(f"[{county}] No parcels at page {page}, stopping", flush=True)
                    break

                page_liens = []
                for item in parcel_data:
                    pid = item['parcel_id']
                    await HumanBehavior.request_delay()

                    try:
                        billed = await self._get_billed_amount(pid)
                    except Exception as e:
                        print(f"[{county}] {pid}: Failed billed amount - {e}", flush=True)
                        billed = item.get('face_amount')  # fallback to auction page

                    try:
                        details = await self._get_parcel_details(pid)
                    except Exception as e:
                        print(f"[{county}] {pid}: Failed parcel details - {e}", flush=True)
                        details = {}

                    assessor_url = f"{self.ASSESSOR_URL}/account.jsp?accountNum={pid}"
                    treasurer_url = f"{self.TREASURER_URL}/account.jsp?account={pid}"

                    lien = {
                        "parcel_id": pid,
                        "address": "{County} County, {State}",
                        "billed_amount": billed,
                        "state": "{State}",
                        "county": "{County}",
                        **details,
                        "google_maps_url": self._build_google_maps_url(details.get("latitude"), details.get("longitude"), details.get("full_address"), pid),
                        "street_view_url": self._build_street_view_url(details.get("latitude"), details.get("longitude"), details.get("full_address")),
                        "assessor_url": assessor_url,
                        "treasurer_url": treasurer_url,
                        "zillow_url": self._build_zillow_url(details.get("full_address"), pid),
                        "realtor_url": self._build_realtor_url(details.get("full_address"), pid),
                    }
                    page_liens.append(lien)
                    total_scraped += 1

                    billed_str = f"${billed:.2f}" if billed else "NULL"
                    print(f"[{county}] {pid}: {billed_str}", flush=True)

                    if limit > 0 and total_scraped >= limit:
                        break

                if on_page_complete and page_liens:
                    on_page_complete(page_liens, page)
                liens.extend(page_liens)

                if limit > 0 and total_scraped >= limit:
                    break

                await HumanBehavior.page_delay()
                page += 1

        except Exception as e:
            print(f"[{county}] Error: {e}", flush=True)
            raise
        finally:
            await self.close()

        return liens
```

### Step 5: Implement The Three Methods

**`_get_auction_page(page_num)`** - extract parcel IDs + face amounts from auction HTML

```python
# Apache pattern: POST with pageNum=, find account= links
parcel_ids = re.findall(r"account=([A-Z0-9]+)", html)

# Coconino pattern: GET with &page=N, find rows with 8-digit IDs
rows = re.findall(r'<tr[^>]*class="highlightRow"[^>]*>(.*?)</tr>', html, re.DOTALL)
```

**`_get_billed_amount(pid)`** - get dollar amount from treasurer
```python
# Apache/Eagle pattern:
match = re.search(r"Total Billed.*?\$\s*([\d,.]+)", html, re.DOTALL | re.IGNORECASE)
```

**`_get_parcel_details(pid)`** - get all property data from assessor
```python
# Call _parse_assessor_html() from base class (once refactored)
# or copy Apache's _get_parcel_details pattern
```

### Step 6: Register The Scraper

```bash
# Add to backend/app/routers/scrapers.py SCRAPER_REGISTRY dict
# Then register via API:
curl -X POST http://localhost:8001/scrapers/config \
  -H "Content-Type: application/json" \
  -d '{"state": "{State}", "county": "{County}", "scraper_name": "app.scrapers.{state_lower}.{county_lower}.{County}Scraper", "scraper_version": "1.0"}'
```

### Step 7: Test With 10 Parcels

```bash
./scrape.sh {State} {County} 10
```

Check output for:
- ✅ All 10 parcels saved (no data loss)
- ✅ `billed_amount` not NULL for most parcels
- ✅ At least some `full_address`, `legal_class` populated
- ✅ No Python errors in `docker logs tax_lien_v2-backend-1`

---

## Arizona County URLs (Known Working)

| County | Auction | Assessor | Treasurer |
|--------|---------|----------|-----------|
| Apache | apache.arizonataxsale.com | eagleassessor.co.apache.az.us | eagletreasurer.co.apache.az.us:8443 |
| Coconino | coconino.arizonataxsale.com | eagleassessor.coconino.az.gov:444 | TBD |
| Maricopa | TBD | mcassessor.maricopa.gov | TBD |
| Pima | TBD | TBD | TBD |
| Yavapai | TBD | TBD | TBD |

---

## Arizona-Specific Notes

- Most AZ counties use **Eagle/TaxWeb** for assessor + treasurer (same login pattern)
- Auction sites are all at `{county}.arizonataxsale.com`
- Guest login works for most: POST `loginPOST.jsp` with `{"submit": "Login", "guest": "true"}`
- Parcel IDs typically: `R` + 7 digits (e.g. `R0012345`) or 8-digit numbers (Coconino)
- `verify=False` required for HTTPS (self-signed certs on Eagle servers)

---

## Immediate Next Steps

1. **Refactor base.py** - move URL builders + `_parse_assessor_html` into base class
2. **Fix Coconino** - wire up `_get_parcel_details` to call `_parse_base_document`
3. **Apply Apache's error handling** to Coconino (try/except per parcel)
4. **Add Maricopa** - largest AZ county, most listings, highest value
5. **Add Pima** - Tucson area, second largest
