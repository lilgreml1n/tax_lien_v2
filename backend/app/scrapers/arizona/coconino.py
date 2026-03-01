"""
Coconino County, Arizona Scraper

Sources:
- Auction listings: https://coconino.arizonataxsale.com/index.cfm?folder=previewitems
- Assessor (parcel + owner details): https://eagleassessor.coconino.az.gov:444/assessor/taxweb

Same EagleSoft assessor system as Apache — HTML patterns are identical.
NOTE: Treasurer integration TBD - billed_amount comes from auction page only.
NOTE: No GIS/ArcGIS endpoint known — lat/lon will be NULL (backfill via ESRI geocoder).
"""
import re
import httpx
from typing import List, Dict, Any, Callable, Optional
from app.scrapers.base import CountyScraper, HumanBehavior


class CoconinaScraper(CountyScraper):

    AUCTION_URL = "https://coconino.arizonataxsale.com/index.cfm?folder=previewitems"
    ASSESSOR_URL = "https://eagleassessor.coconino.az.gov:444/assessor/taxweb"

    def __init__(self, state: str, county: str):
        super().__init__(state, county)
        self.assessor_cookies = None

    async def scrape(self, limit: int = 0, start_page: int = 1,
                     on_page_complete: Optional[Callable] = None) -> List[Dict[str, Any]]:
        liens = []
        total_scraped = 0
        try:
            await self._login_assessor()

            page = start_page
            max_pages = 500  # Safety limit (will stop when no parcels found)

            if start_page > 1:
                print(f"[Coconino] Resuming from page {start_page}", flush=True)

            while page <= max_pages:
                print(f"[Coconino] Fetching page {page}...", flush=True)

                parcel_data = await self._get_auction_page(page)
                if not parcel_data:
                    print(f"[Coconino] No parcels at page {page}, stopping", flush=True)
                    break

                page_liens = []
                for parcel in parcel_data:
                    pid = parcel['parcel_id']
                    face_amount = parcel['face_amount']
                    await HumanBehavior.request_delay()

                    # Get parcel details from assessor
                    details = await self._get_parcel_details(pid)

                    # Build URLs
                    assessor_url = f"{self.ASSESSOR_URL}/account.jsp?accountNum={pid}"

                    # Build Google Maps URL
                    google_maps_url = self._build_google_maps_url(
                        details.get("latitude"),
                        details.get("longitude"),
                        details.get("full_address"),
                        pid
                    )

                    # Build Street View URL
                    street_view_url = self._build_street_view_url(
                        details.get("latitude"),
                        details.get("longitude"),
                        details.get("full_address")
                    )

                    # Build Zillow and Realtor URLs
                    zillow_url = self._build_zillow_url(details.get("full_address"), pid)
                    realtor_url = self._build_realtor_url(details.get("full_address"), pid)

                    lien = {
                        "parcel_id": pid,
                        "address": "Coconino County, AZ",  # Keep for backward compatibility
                        "billed_amount": face_amount,  # NOW FROM AUCTION PAGE
                        "state": "Arizona",
                        "county": "Coconino",
                        # Merge all details
                        **details,
                        # URLs
                        "google_maps_url": google_maps_url,
                        "street_view_url": street_view_url,
                        "assessor_url": assessor_url,
                        "treasurer_url": None,  # TODO: Add Treasurer URL
                        "zillow_url": zillow_url,
                        "realtor_url": realtor_url,
                    }
                    page_liens.append(lien)
                    total_scraped += 1

                    # Enhanced logging
                    owner_str = details.get('owner_name', '?')[:30] if details.get('owner_name') else '?'
                    billed_str = f"${face_amount:,.2f}" if face_amount else "?"
                    value_str = f"${int(details.get('assessed_total_value'))}" if details.get('assessed_total_value') else "?"
                    print(f"[Coconino] {pid}: Billed={billed_str}, Owner={owner_str}, Value={value_str}", flush=True)

                    if limit > 0 and total_scraped >= limit:
                        print(f"[Coconino] Reached limit of {limit}", flush=True)
                        break

                # Notify callback with this page's parcels
                if on_page_complete and page_liens:
                    on_page_complete(page_liens, page)

                liens.extend(page_liens)

                if limit > 0 and total_scraped >= limit:
                    break

                await HumanBehavior.page_delay()
                page += 1

            self.total_parcels_available = total_scraped  # Best estimate after full run
            print(f"[Coconino] Scraped {len(liens)} total", flush=True)
        except Exception as e:
            print(f"[Coconino] Error: {e}", flush=True)
            raise
        finally:
            await self.close()

        return liens

    async def _login_assessor(self):
        print("[Coconino] Logging into Assessor...", flush=True)
        if not self.session:
            self.session = httpx.AsyncClient(timeout=30.0, verify=False)
        headers = HumanBehavior.get_headers()
        response = await self.session.post(
            f"{self.ASSESSOR_URL}/loginPOST.jsp",
            data={"submit": "Login", "guest": "true"},
            headers=headers,
            follow_redirects=True,
        )
        self.assessor_cookies = response.cookies

    async def _get_auction_page(self, page_num: int) -> List[Dict[str, Any]]:
        """Get parcel IDs and Face Amount (billed amount) from auction page"""
        if not self.session:
            self.session = httpx.AsyncClient(timeout=30.0, verify=False)
        headers = HumanBehavior.get_headers()

        # Coconino requires proper pagination via JavaScript function
        # Page 1 = default, page 2+ use ?page=N parameter
        if page_num == 1:
            url = self.AUCTION_URL
        else:
            url = f"{self.AUCTION_URL}&page={page_num}"

        response = await self.session.get(
            url,
            headers=headers,
            follow_redirects=True,
        )

        # Extract table rows to get both parcel ID and Face Amount
        # Table format: <tr>...<td>parcel_id</td>...<td>$face_amount</td>...</tr>
        parcels = []

        # Find all table rows with parcel data
        rows = re.findall(r'<tr[^>]*class="highlightRow"[^>]*>(.*?)</tr>', response.text, re.DOTALL)

        for row in rows:
            # Extract parcel ID (8 digits + optional letter)
            pid_match = re.search(r'([0-9]{8}[A-Z]?)', row)
            if not pid_match:
                continue

            pid = pid_match.group(1)

            # Skip invalid IDs (years, etc.)
            if pid.startswith(('2024', '2023', '2022', '2021', '2020')):
                continue

            # Extract Face Amount: $XX,XXX.XX
            face_amount = None
            amount_match = re.search(r'\$\s*([\d,]+(?:\.\d{2})?)', row)
            if amount_match:
                try:
                    face_amount = float(amount_match.group(1).replace(',', ''))
                except ValueError:
                    pass

            parcels.append({
                'parcel_id': pid,
                'face_amount': face_amount,
            })

        # Remove duplicates (keep first occurrence)
        seen = set()
        unique_parcels = []
        for p in parcels:
            if p['parcel_id'] not in seen:
                unique_parcels.append(p)
                seen.add(p['parcel_id'])

        return unique_parcels

    async def _get_parcel_details(self, pid: str) -> dict:
        """Get parcel details from Coconino EagleAssessor.

        Same EagleSoft system as Apache — HTML patterns are identical.
        Fetches TWO pages per parcel:
          1. Summary page — owner, address, legal class, FCV, legal description
          2. Parcel Detail sub-doc — lot size (not on summary page)
        """
        if not self.session:
            self.session = httpx.AsyncClient(timeout=30.0, verify=False)

        details = {
            "legal_class": "Unknown",
            "full_address": None,
            "latitude": None,
            "longitude": None,
            "lot_size_acres": None,
            "lot_size_sqft": None,
            "zoning_code": None,
            "zoning_description": None,
            "assessed_land_value": None,
            "assessed_improvement_value": None,
            "assessed_total_value": None,
            "legal_description": None,
            "owner_name": None,
            "owner_mailing_address": None,
        }

        try:
            url = f"{self.ASSESSOR_URL}/account.jsp?accountNum={pid}"
            response = await self.session.get(
                url, cookies=self.assessor_cookies,
                headers=HumanBehavior.get_headers(), follow_redirects=True
            )
            html = response.text
        except Exception as e:
            print(f"[Coconino] {pid}: assessor fetch failed - {e}", flush=True)
            return details

        # Legal Class
        match = re.search(r"Legal Class.*?<td[^>]*>([^<]+)</td>", html, re.DOTALL | re.IGNORECASE)
        if match:
            details["legal_class"] = match.group(1).strip()

        # Situs Address
        match = re.search(r"<strong>Situs\s+Address</strong>\s*([^<]*)", html)
        if match:
            addr = match.group(1).strip()
            if len(addr) > 3:
                details["full_address"] = addr

        # Owner Name
        match = re.search(r"<b>Owner\s+Name</b>\s*([^\n<]+)", html)
        if match:
            name = match.group(1).strip()
            if len(name) > 2:
                details["owner_name"] = name[:255]

        # Owner Mailing Address
        match = re.search(r"<b>Owner\s+Address</b>\s*((?:[^<]|<br[^>]*>)+)", html)
        if match:
            raw = match.group(1)
            addr = re.sub(r"<br[^>]*>", " ", raw).strip()
            addr = re.sub(r"\s+", " ", addr)
            if len(addr) > 5:
                details["owner_mailing_address"] = addr[:500]

        # Full Cash Value (FCV) → assessed_total_value
        match = re.search(r"Full Cash Value \(FCV\)</b><td[^>]*>\$?([\d,]+)", html)
        if match:
            try:
                details["assessed_total_value"] = float(match.group(1).replace(",", ""))
            except ValueError:
                pass

        # Legal Description
        match = re.search(r"Legal Summary[^<]*(?:<[^>]+>)*</strong>\s*([^<]+)", html)
        if match:
            desc = re.sub(r"\s+", " ", match.group(1).strip())
            if len(desc) > 5:
                details["legal_description"] = desc[:1000]

        # Parcel Detail sub-doc — lot size lives here
        doc_match = re.search(
            r'href="account\.jsp\?accountNum=[^&]+&doc=([^"]+)">Parcel Detail', html
        )
        if doc_match:
            doc_id = doc_match.group(1)
            try:
                await HumanBehavior.request_delay()
                detail_url = f"{self.ASSESSOR_URL}/account.jsp?accountNum={pid}&doc={doc_id}"
                detail_resp = await self.session.get(
                    detail_url, cookies=self.assessor_cookies,
                    headers=HumanBehavior.get_headers(), follow_redirects=True
                )
                detail_html = detail_resp.text

                size_match = re.search(
                    r"Parcel Size</span><br[^/]*/><span[^>]*><span[^>]*>([\d.]+)", detail_html
                )
                unit_match = re.search(
                    r"Unit of Measure</span><br[^/]*/><span[^>]*><span[^>]*>([^&<]+)", detail_html
                )
                if size_match and unit_match:
                    size_val = float(size_match.group(1))
                    unit = unit_match.group(1).strip().lower()
                    if "acre" in unit and 0.001 <= size_val <= 100000:
                        details["lot_size_acres"] = size_val
                        details["lot_size_sqft"] = int(size_val * 43560)
                    elif ("sq" in unit or "feet" in unit) and 100 <= size_val <= 500000000:
                        details["lot_size_sqft"] = int(size_val)
                        details["lot_size_acres"] = round(size_val / 43560, 4)
                elif size_match:
                    size_val = float(size_match.group(1))
                    if 0.001 <= size_val <= 10000:
                        details["lot_size_acres"] = size_val
                        details["lot_size_sqft"] = int(size_val * 43560)
            except Exception as e:
                print(f"[Coconino] {pid}: Parcel Detail sub-doc failed - {e}", flush=True)

        return details

    def _build_google_maps_url(self, lat: float = None, lon: float = None, address: str = None, parcel_id: str = None) -> str:
        """Build Google Maps URL from coordinates or address"""
        if lat and lon:
            return f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
        elif address:
            import urllib.parse
            encoded_address = urllib.parse.quote(address)
            return f"https://www.google.com/maps/search/?api=1&query={encoded_address}"
        elif parcel_id:
            return f"https://www.google.com/maps/search/?api=1&query=Parcel+{parcel_id}+Coconino+County+Arizona"
        else:
            return "https://www.google.com/maps/search/?api=1&query=Coconino+County+Arizona"

    def _build_street_view_url(self, lat: float = None, lon: float = None, address: str = None) -> str:
        """Build Google Street View URL"""
        if lat and lon:
            return f"https://www.google.com/maps/@{lat},{lon},3a,75y,0h,90t/data=!3m6!1e1!3m4!1s0!2e0!7i13312!8i6656"
        elif address:
            import urllib.parse
            encoded = urllib.parse.quote(address)
            return f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=&pano={encoded}"
        else:
            return None

    def _build_zillow_url(self, address: str = None, parcel_id: str = None) -> str:
        """Build Zillow property page URL"""
        if address:
            import urllib.parse
            encoded = urllib.parse.quote(address)
            return f"https://www.zillow.com/homes/{encoded}_rb/"
        elif parcel_id:
            return f"https://www.zillow.com/homes/Parcel-{parcel_id}-Coconino-County-AZ_rb/"
        else:
            return None

    def _build_realtor_url(self, address: str = None, parcel_id: str = None) -> str:
        """Build Realtor.com property page URL"""
        if address:
            import urllib.parse
            encoded = urllib.parse.quote(address)
            return f"https://www.realtor.com/realestateandhomes-search/{encoded}"
        elif parcel_id:
            return f"https://www.realtor.com/realestateandhomes-search/Coconino-County_AZ/parcel-{parcel_id}"
        else:
            return None
