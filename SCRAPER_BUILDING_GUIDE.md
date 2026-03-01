# Tax Lien Scraper Building Guide for Gemini

**Purpose**: Uniform, templated approach to building county tax lien scrapers.
**For**: Gemini (straightforward scrapers) | Claude (complex cases, edge cases, debugging)

---

## PHASE 0: AUTONOMOUS DISCOVERY (GEMINI ONLY)

### 1. Automated Discovery Script
Before building any scraper, run the `scout_counties.py` script to automatically find PDFs and Excel lists for the target state/county.

```bash
# Install playwright if not ready
# pip install playwright && playwright install chromium

# Run discovery for Nebraska (example)
python scripts/scout_counties.py
```

This script will:
- Search Google for specific filetypes (PDF/XLSX)
- Visit state-level portals (e.g., NE Dept of Revenue)
- Update `SCRAPER_RESULTS.md` with URLs and formats.

### 2. Triple-Search Protocol (Manual)
If the script doesn't find what you need, execute:
- Search 1: `"[County] [State] delinquent real estate tax list 2026 filetype:pdf OR filetype:xlsx"`
- Search 2: `"[County] [State] tax sale auction rules 2026"`
- Search 3: `"[County] [State] property search sample parcel ID"`

### 3. Platform ID
Determine if the county uses a known portal:
- **Beacon/Schneider**: Section B template
- **Orion/Tyler**: Section B template
- **gWorks/SIMS**: Section B (Playwright likely)
- **Realauction**: Section B (Playwright likely)
- **iPlow**: Commonly used in Nebraska (e.g., Douglas/Sarpy)

### 4. Parcel Format Check
Locate a real parcel on the Assessor site to verify the ID format (e.g., `XX-XX-XXX`) before writing any regex.

### 5. Bot Check
Use `curl -I` or `web_fetch` to see if the site blocks bots. If it returns 403 or a Cloudflare page, skip simple templates and use Playwright or escalate to Claude.

---

## DECISION TREE: Which Scraper Type?

```
Is the parcel list in a FILE (PDF, Excel)?
├─ YES → Go to SECTION A: PDF/Excel Scrapers
│        (Fast, high accuracy, no pagination)
│
└─ NO → Is it an HTML page with pagination?
        ├─ YES → Go to SECTION B: HTML Paginated Scrapers
        │        (Common for arizonataxsale.com, Beacon)
        │
        └─ NO → Is it JavaScript-heavy or Cloudflare-protected?
                ├─ YES → Escalate to Claude (needs Playwright/session handling)
                │
                └─ NO → Go to SECTION C: Simple HTML Scrapers
```

---

## SECTION A: PDF/Excel Scrapers

**Use when:** Parcel list is in a downloadable file (PDF, .xlsx)

**Characteristics:**
- Total parcel count known BEFORE pagination
- No HTTP requests per parcel during file parsing
- Simple HTTP requests to assessor/treasurer AFTER list is parsed
- Set `self.total_parcels_available = len(all_parcels)` BEFORE applying limit

**Examples:** Lancaster (PDF), Mohave (Excel)

### Template: PDF Scraper

```python
import re
import httpx
import pdfplumber
import io
from typing import List, Dict, Any, Callable, Optional
from app.scrapers.base import CountyScraper, HumanBehavior, with_retry

class CountyScraper(CountyScraper):
    """
    {County}, {State} Scraper

    Source: {PDF URL}
    Parcel format: {e.g., 16-16-320-001-000}
    """

    PDF_URL = "{full_url}"
    ASSESSOR_BASE_URL = "{url}"

    # Regex to match parcel lines in PDF text
    PARCEL_RE = re.compile(
        r'^\S+\s+.{1,50}\s+(B[\w]{3,6})\s+(L\d{1,4}(?:\s+[A-Z])?)\s+(\d{2}-\d{2}-\d{3}-\d{3}-\d{3})\s+'
        r'([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+(.{1,65}?)\s*([A-Z][A-Z0-9]{0,3})\s*$',
        re.MULTILINE
    )

    def __init__(self, state: str = "{State}", county: str = "{County}"):
        super().__init__(state, county)

    async def scrape(self, limit: int = 0, start_page: int = 1,
                     on_page_complete: Optional[Callable] = None) -> List[Dict[str, Any]]:
        """Download PDF, parse it, return parcels."""
        all_parcels: List[Dict[str, Any]] = []

        async with httpx.AsyncClient(timeout=60.0, verify=False) as client:
            print(f"[{self.county}] Downloading PDF...", flush=True)
            try:
                await HumanBehavior.request_delay()
                resp = await client.get(self.PDF_URL, headers=HumanBehavior.get_headers(),
                                      follow_redirects=True)
                resp.raise_for_status()
                text = self._extract_pdf_text(resp.content)
                parcels = self._parse_pdf_text(text)
                print(f"[{self.county}] Parsed {len(parcels)} parcels", flush=True)
                all_parcels.extend(parcels)
            except Exception as e:
                print(f"[{self.county}] Error: {e}", flush=True)

        # CRITICAL: Set total BEFORE applying limit
        self.total_parcels_available = len(all_parcels)

        if limit > 0:
            all_parcels = all_parcels[:limit]

        print(f"[{self.county}] Total: {len(all_parcels)} (available: {self.total_parcels_available})", flush=True)

        # Fire callback so API saves them
        if on_page_complete and all_parcels:
            on_page_complete(all_parcels, 1)

        return all_parcels

    def _extract_pdf_text(self, pdf_bytes: bytes) -> str:
        """Extract layout-preserved text from PDF."""
        text_parts = []
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                text = page.extract_text(layout=True)
                if text:
                    text_parts.append(text)
        return "\n".join(text_parts)

    def _parse_pdf_text(self, text: str) -> List[Dict[str, Any]]:
        """Parse PDF text into parcel dicts."""
        parcels = []
        lines = text.split("\n")

        for i, line in enumerate(lines):
            m = self.PARCEL_RE.match(line.strip())
            if not m:
                continue

            parcel_id = m.group(3)
            billed = float(m.group(4).replace(",", ""))
            taxable = float(m.group(5).replace(",", ""))
            address = m.group(7).strip()
            legal_class = m.group(8).strip()

            # Extract owner name from next line (if exists)
            owner_name = None
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line and not self.PARCEL_RE.match(next_line):
                    owner_match = re.match(r'^(.{3,40?})\s{3,}', next_line)
                    owner_name = owner_match.group(1).strip() if owner_match else next_line[:40].strip()

            parcels.append({
                "state": self.state,
                "county": self.county,
                "parcel_id": parcel_id,
                "billed_amount": billed,
                "assessed_total_value": taxable,
                "full_address": address if address and "NO SITUS" not in address else None,
                "owner_name": owner_name,
                "legal_class": legal_class,
                "source_url": self.PDF_URL,
                "assessor_url": f"{self.ASSESSOR_BASE_URL}/{parcel_id.replace('-', '')}",
                # These come from backfill
                "latitude": None,
                "longitude": None,
                "lot_size_acres": None,
                "lot_size_sqft": None,
                "assessed_land_value": None,
                "assessed_improvement_value": None,
                "legal_description": None,
                "owner_mailing_address": None,
                "zoning_code": None,
                "zoning_description": None,
                "google_maps_url": None,
                "street_view_url": None,
                "zillow_url": None,
                "realtor_url": None,
                "treasurer_url": None,
            })

        return parcels

    # ── Assessor Backfill ──────────────────────────────────────────

    async def _login_assessor(self):
        """Initialize assessor session (override if login needed)."""
        if not self.session:
            self.session = httpx.AsyncClient(timeout=30.0, verify=False)
        await self.session.get(self.ASSESSOR_BASE_URL, headers=HumanBehavior.get_headers())

    async def _login_treasurer(self):
        """Not used for this county."""
        pass

    async def _get_parcel_details(self, pid: str) -> dict:
        """Fetch property details from assessor."""
        if not self.session:
            self.session = httpx.AsyncClient(timeout=30.0, verify=False)

        details = {
            "owner_name": None,
            "owner_mailing_address": None,
            "full_address": None,
            "assessed_total_value": None,
            "assessed_land_value": None,
            "assessed_improvement_value": None,
            "legal_description": None,
            "lot_size_acres": None,
            "legal_class": None,
        }

        url = f"{self.ASSESSOR_BASE_URL}/{pid.replace('-', '')}"

        try:
            await HumanBehavior.request_delay()
            resp = await self.session.get(url, headers=HumanBehavior.get_headers(),
                                         follow_redirects=True)
            html = resp.text

            # Parse HTML using regex (simple) or BeautifulSoup (complex)
            # TODO: Add regex patterns for your specific assessor site

        except Exception as e:
            print(f"[{self.county}] {pid}: {e}", flush=True)

        return details

    async def close(self):
        if self.session:
            await self.session.aclose()
            self.session = None
```

---

## SECTION B: HTML Paginated Scrapers

**Use when:** Parcel list is on an HTML page with pagination (no file download)

**Characteristics:**
- Total parcel count NOT known upfront (set to 0 during in_progress, actual count on completion)
- HTTP request per page to fetch parcel list
- Additional HTTP requests per parcel for details
- Common on: arizonataxsale.com, county assessor sites

**Examples:** Apache, Coconino, Yavapai

### Template: HTML Paginated Scraper

```python
import re
import httpx
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional, Callable
from app.scrapers.base import CountyScraper, HumanBehavior, with_retry

class CountyScraper(CountyScraper):
    """
    {County}, {State} Scraper

    Auction site: {URL}
    Assessor: {URL}
    Parcel format: {e.g., R0012345}
    """

    AUCTION_URL = "{full_url}"
    ASSESSOR_URL = "{url}"
    TREASURER_URL = "{url}"

    PARCEL_ID_PATTERN = re.compile(r'{REGEX}')  # Extract parcel ID from page

    def __init__(self, state: str = "{State}", county: str = "{County}"):
        super().__init__(state, county)

    async def scrape(self, limit: int = 0, start_page: int = 1,
                     on_page_complete: Optional[Callable] = None) -> List[Dict[str, Any]]:
        """Scrape paginated auction site."""
        all_liens = []
        total_scraped = 0

        try:
            await self._login_treasurer()
            await self._login_assessor()

            page = start_page
            max_pages = 200  # Reasonable upper bound

            while page <= max_pages:
                print(f"[{self.county}] Fetching page {page}...", flush=True)

                parcel_ids = await with_retry(
                    lambda: self._get_auction_page(page),
                    label=f"{self.county} page {page}",
                    max_wait=300,
                    retry_delay=30,
                )

                if not parcel_ids:
                    print(f"[{self.county}] No parcels at page {page}, stopping", flush=True)
                    break

                page_liens = []
                for pid in parcel_ids:
                    await HumanBehavior.request_delay()

                    try:
                        details = await with_retry(
                            lambda: self._get_parcel_details(pid),
                            label=f"{self.county} {pid}",
                            max_wait=300,
                            retry_delay=30,
                        )
                    except Exception as e:
                        print(f"[{self.county}] {pid}: {e}", flush=True)
                        details = {}

                    page_liens.append({
                        "state": self.state,
                        "county": self.county,
                        "parcel_id": pid,
                        "billed_amount": details.get("billed_amount"),
                        "assessed_total_value": details.get("assessed_total_value"),
                        "full_address": details.get("full_address"),
                        "owner_name": details.get("owner_name"),
                        "legal_class": details.get("legal_class"),
                        "source_url": self.AUCTION_URL,
                        "assessor_url": details.get("assessor_url"),
                        # ... other fields initialized to None
                    })

                    total_scraped += 1
                    if limit > 0 and total_scraped >= limit:
                        break

                all_liens.extend(page_liens)

                if on_page_complete:
                    on_page_complete(page_liens, page)

                if limit > 0 and total_scraped >= limit:
                    break

                await HumanBehavior.page_delay()
                page += 1

            # Set total AFTER loop finishes (best estimate)
            self.total_parcels_available = total_scraped
            print(f"[{self.county}] Scraped {len(all_liens)} total", flush=True)

        except Exception as e:
            print(f"[{self.county}] Error: {e}", flush=True)
            raise
        finally:
            await self.close()

        return all_liens

    async def _get_auction_page(self, page: int) -> List[str]:
        """Fetch parcel IDs from a single auction page."""
        # TODO: Implement page fetch and ID extraction
        pass

    async def _login_treasurer(self):
        """Initialize treasurer session."""
        if not self.session:
            self.session = httpx.AsyncClient(timeout=30.0, verify=False)
        # Optionally: fetch homepage to set cookies

    async def _login_assessor(self):
        """Initialize assessor session."""
        if not self.session:
            self.session = httpx.AsyncClient(timeout=30.0, verify=False)

    async def _get_parcel_details(self, pid: str) -> dict:
        """Fetch details for one parcel."""
        # TODO: Implement per-parcel fetch
        pass

    async def close(self):
        if self.session:
            await self.session.aclose()
            self.session = None
```

---

## SECTION C: Simple HTML Scrapers

**Use when:** Single-page HTML with all parcels or simple lookup (no complex pagination)

**Examples:** Some small county sites

**⚠️ Escalate to Claude if:**
- Site requires Playwright (JavaScript rendering)
- Session/cookie handling is complex
- Cloudflare or bot detection present

---

## MANDATORY CHECKLIST

Every scraper MUST:

- [ ] Set `self.total_parcels_available = N` (PDF/Excel: before limit; HTML: after loop)
- [ ] Have `_login_assessor()` and `_login_treasurer()` methods (even if just pass)
- [ ] Have `_get_parcel_details(pid)` returning a dict with at least: `owner_name`, `billed_amount`, `assessed_total_value`, `legal_class`
- [ ] Use `HumanBehavior.request_delay()` and `HumanBehavior.page_delay()` between requests
- [ ] Wrap all network calls in `with_retry()`
- [ ] Per-parcel try/except with silent failure (NULL fallback, don't drop rows)
- [ ] Fire `on_page_complete(page_liens, page_num)` callback (even if only once for PDF/Excel)
- [ ] Initialize all fields in the parcel dict (NULL is fine for backfill-only fields)
- [ ] Call `await self.close()` in finally block

---

## REGISTRATION & TESTING

After building the scraper:

```bash
# 1. Register via API
curl -X POST "http://localhost:8001/scrapers/config" \
  -H "Content-Type: application/json" \
  -d '{"state":"XX","county":"YY","scraper_name":"app.scrapers.xx.yy.YYScraper","scraper_version":"1.0"}'

# 2. Test with limit
curl -X POST "http://localhost:8001/scrapers/scrape/XX/YY?limit=10"

# 3. Check logs
docker logs -f tax_lien_v2-backend-1 | grep "\[YY\]"

# 4. Full scrape
./scrape.sh XX YY
```

---

## WHEN TO ESCALATE TO CLAUDE

❌ **Don't escalate simple stuff**:
- Adding a new regex pattern
- Adjusting HTML parsing for similar site structure
- Adding assessor backfill for a Beacon/EagleSoft-like system

✅ **DO escalate**:
- Site requires Playwright / JavaScript rendering
- Cloudflare or advanced bot detection
- Complex session management or multi-step login
- Custom auth (2FA, API keys, etc.)
- Edge case parcel ID formats
- Data in iframes, PDFs, or unconventional locations
- Multi-county unified platform with unusual structure

---

## QUICK REFERENCE: Field Mapping

**Always include in parcel dict:**

| Field | Type | Required | Notes |
|---|---|---|---|
| `state` | str | YES | e.g., "Arizona" |
| `county` | str | YES | e.g., "Apache" |
| `parcel_id` | str | YES | Must be unique per county |
| `billed_amount` | float | YES | Amount owed (lien amount) |
| `assessed_total_value` | float | Optional | For AI scoring (Gate 2) |
| `full_address` | str | Optional | NULL if "NO SITUS" or missing |
| `owner_name` | str | Optional | For AI kill switch check |
| `legal_class` | str | Optional | For AI Gate 1 check |
| `source_url` | str | YES | Where parcel came from |
| `assessor_url` | str | Optional | For backfill |
| All other fields | - | Optional | Initialize to None; backfill fills them |

---

## EXAMPLE: Lancaster (PDF) Walk-through

1. Download PDF from `PDF_URL`
2. Parse with pdfplumber → text
3. Regex match each parcel line → extract (parcel_id, billed, taxable, address, class)
4. Owner name from next line (if present)
5. Set `self.total_parcels_available = len(unique_parcels)` BEFORE limit
6. Call `on_page_complete(parcels, 1)` (single batch)
7. Return parcels

---

## EXAMPLE: Apache (HTML Paginated) Walk-through

1. Fetch page 1 → extract parcel IDs using regex
2. For each parcel ID:
   - Fetch treasurer page (billed amount)
   - Fetch assessor page (owner, values)
   - Combine into parcel dict
3. Fire `on_page_complete(page_parcels, page)` callback
4. Move to page 2, repeat
5. When no more pages, set `self.total_parcels_available = total_scraped`
6. Return all_liens

---

**Last updated:** 2026-02-28
**Next revision:** After Yavapai assessor wiring complete
