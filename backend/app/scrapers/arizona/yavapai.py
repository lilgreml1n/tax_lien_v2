"""
Yavapai County, Arizona Scraper

Sources:
- Auction listings: https://yavapai.arizonataxsale.com/index.cfm?folder=previewitems
- Assessor: TODO — assessor.yavapai.us did not load pre-auction.
            Confirm URL and parcel ID format Monday 03/02/2026 when list goes live.

Same arizonataxsale.com platform as Apache/Coconino — auction scraping is identical.
Assessor is stubbed — returns NULLs until wired up Monday.

TODO Monday 03/02/2026:
  1. Open the live auction list, grab a parcel ID — confirm format (dashes? digits only?)
  2. Find the working assessor URL (try assessor.yavapai.us or yavapai.us/assessor)
  3. Load one parcel on the assessor — confirm field labels (same EagleSoft? different system?)
  4. Update PARCEL_ID_PATTERN, ASSESSOR_URL, and _get_parcel_details() below
  5. Run: curl -X POST "http://localhost:8001/scrapers/scrape/Arizona/Yavapai?limit=5"
"""
import re
import httpx
from typing import List, Dict, Any, Callable, Optional
from app.scrapers.base import CountyScraper, HumanBehavior


class YavapaiScraper(CountyScraper):

    AUCTION_URL = "https://yavapai.arizonataxsale.com/index.cfm?folder=previewitems"

    # TODO: confirm correct assessor URL Monday
    ASSESSOR_URL = None

    # TODO: confirm parcel ID format Monday
    # Common AZ formats: 8 digits (10523456), dashes (301-26-027), R+7digits (R0012345)
    # Current pattern catches all three — tighten after seeing real IDs
    PARCEL_ID_PATTERN = re.compile(r'(\d{3}-\d{2,3}-\d{3}[A-Z]?|\d{8}[A-Z]?|R\d{7})')

    def __init__(self, state: str, county: str):
        super().__init__(state, county)
        self.assessor_cookies = None

    async def scrape(self, limit: int = 0, start_page: int = 1,
                     on_page_complete: Optional[Callable] = None) -> List[Dict[str, Any]]:
        liens = []
        total_scraped = 0
        try:
            page = start_page
            max_pages = 500

            if start_page > 1:
                print(f"[Yavapai] Resuming from page {start_page}", flush=True)

            while page <= max_pages:
                print(f"[Yavapai] Fetching page {page}...", flush=True)

                parcel_data = await self._get_auction_page(page)
                if not parcel_data:
                    print(f"[Yavapai] No parcels at page {page}, stopping", flush=True)
                    break

                page_liens = []
                for parcel in parcel_data:
                    pid = parcel['parcel_id']
                    face_amount = parcel['face_amount']
                    await HumanBehavior.request_delay()

                    details = await self._get_parcel_details(pid)

                    assessor_url = (
                        f"{self.ASSESSOR_URL}/account.jsp?accountNum={pid}"
                        if self.ASSESSOR_URL else None
                    )

                    google_maps_url = self._build_google_maps_url(
                        details.get("latitude"), details.get("longitude"),
                        details.get("full_address"), pid
                    )
                    street_view_url = self._build_street_view_url(
                        details.get("latitude"), details.get("longitude"),
                        details.get("full_address")
                    )
                    zillow_url  = self._build_zillow_url(details.get("full_address"), pid)
                    realtor_url = self._build_realtor_url(details.get("full_address"), pid)

                    lien = {
                        "parcel_id":    pid,
                        "address":      "Yavapai County, AZ",
                        "billed_amount": face_amount,
                        "state":        "Arizona",
                        "county":       "Yavapai",
                        **details,
                        "google_maps_url":  google_maps_url,
                        "street_view_url":  street_view_url,
                        "assessor_url":     assessor_url,
                        "treasurer_url":    None,
                        "zillow_url":       zillow_url,
                        "realtor_url":      realtor_url,
                    }
                    page_liens.append(lien)
                    total_scraped += 1

                    owner_str  = (details.get('owner_name') or '?')[:30]
                    billed_str = f"${face_amount:,.2f}" if face_amount else "?"
                    value_str  = f"${int(details.get('assessed_total_value'))}" if details.get('assessed_total_value') else "?"
                    print(f"[Yavapai] {pid}: Billed={billed_str}, Owner={owner_str}, Value={value_str}", flush=True)

                    if limit > 0 and total_scraped >= limit:
                        print(f"[Yavapai] Reached limit of {limit}", flush=True)
                        break

                if on_page_complete and page_liens:
                    on_page_complete(page_liens, page)

                liens.extend(page_liens)

                if limit > 0 and total_scraped >= limit:
                    break

                await HumanBehavior.page_delay()
                page += 1

            self.total_parcels_available = total_scraped  # Best estimate after full run
            print(f"[Yavapai] Scraped {len(liens)} total", flush=True)
        except Exception as e:
            print(f"[Yavapai] Error: {e}", flush=True)
            raise
        finally:
            await self.close()

        return liens

    async def _get_auction_page(self, page_num: int) -> List[Dict[str, Any]]:
        """Identical platform to Apache/Coconino — same HTML structure."""
        if not self.session:
            self.session = httpx.AsyncClient(timeout=30.0, verify=False)

        url = self.AUCTION_URL if page_num == 1 else f"{self.AUCTION_URL}&page={page_num}"
        response = await self.session.get(url, headers=HumanBehavior.get_headers(), follow_redirects=True)

        parcels = []
        rows = re.findall(r'<tr[^>]*class="highlightRow"[^>]*>(.*?)</tr>', response.text, re.DOTALL)

        for row in rows:
            pid_match = self.PARCEL_ID_PATTERN.search(row)
            if not pid_match:
                continue
            pid = pid_match.group(1)

            # Skip year-like values
            if re.match(r'20\d{2}', pid):
                continue

            face_amount = None
            amount_match = re.search(r'\$\s*([\d,]+(?:\.\d{2})?)', row)
            if amount_match:
                try:
                    face_amount = float(amount_match.group(1).replace(',', ''))
                except ValueError:
                    pass

            parcels.append({'parcel_id': pid, 'face_amount': face_amount})

        # Deduplicate
        seen = set()
        unique = []
        for p in parcels:
            if p['parcel_id'] not in seen:
                unique.append(p)
                seen.add(p['parcel_id'])

        return unique

    async def _get_parcel_details(self, pid: str) -> dict:
        """
        Assessor lookup — STUBBED until Monday 03/02/2026.
        Wire up after confirming assessor URL and field labels from live parcel.
        """
        # TODO: implement after confirming assessor system Monday
        return {
            "legal_class":                 None,
            "full_address":                None,
            "latitude":                    None,
            "longitude":                   None,
            "lot_size_acres":              None,
            "lot_size_sqft":               None,
            "zoning_code":                 None,
            "zoning_description":          None,
            "assessed_land_value":         None,
            "assessed_improvement_value":  None,
            "assessed_total_value":        None,
            "legal_description":           None,
            "owner_name":                  None,
            "owner_mailing_address":       None,
        }

    def _build_google_maps_url(self, lat=None, lon=None, address=None, parcel_id=None):
        import urllib.parse
        if lat and lon:
            return f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
        if address:
            return f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(address)}"
        return f"https://www.google.com/maps/search/?api=1&query=Parcel+{parcel_id}+Yavapai+County+Arizona"

    def _build_street_view_url(self, lat=None, lon=None, address=None):
        import urllib.parse
        if lat and lon:
            return f"https://www.google.com/maps/@{lat},{lon},3a,75y,0h,90t/data=!3m6!1e1!3m4!1s0!2e0!7i13312!8i6656"
        if address:
            return f"https://www.google.com/maps/@?api=1&map_action=pano&pano={urllib.parse.quote(address)}"
        return None

    def _build_zillow_url(self, address=None, parcel_id=None):
        import urllib.parse
        if address:
            return f"https://www.zillow.com/homes/{urllib.parse.quote(address)}_rb/"
        return f"https://www.zillow.com/homes/Parcel-{parcel_id}-Yavapai-County-AZ_rb/"

    def _build_realtor_url(self, address=None, parcel_id=None):
        import urllib.parse
        if address:
            return f"https://www.realtor.com/realestateandhomes-search/{urllib.parse.quote(address)}"
        return f"https://www.realtor.com/realestateandhomes-search/Yavapai-County_AZ/parcel-{parcel_id}"
