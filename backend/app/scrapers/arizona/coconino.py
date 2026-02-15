"""
Coconino County, Arizona Scraper

Sources:
- Auction listings: https://coconino.arizonataxsale.com/index.cfm?folder=previewitems
- Assessor (parcel + owner details): https://eagleassessor.coconino.az.gov:444/assessor/taxweb

NOTE: Treasurer integration TBD - billed_amount will be NULL for now
"""
import re
import httpx
from typing import List, Dict, Any
from app.scrapers.base import CountyScraper, HumanBehavior


class CoconinoCraper(CountyScraper):

    AUCTION_URL = "https://coconino.arizonataxsale.com/index.cfm?folder=previewitems"
    ASSESSOR_URL = "https://eagleassessor.coconino.az.gov:444/assessor/taxweb"

    def __init__(self, state: str, county: str):
        super().__init__(state, county)
        self.assessor_cookies = None

    async def scrape(self, limit: int = 0) -> List[Dict[str, Any]]:
        liens = []
        try:
            await self._login_assessor()

            page = 1
            max_pages = 500  # Safety limit (will stop when no parcels found)

            while page <= max_pages:
                print(f"[Coconino] Fetching page {page}...", flush=True)

                parcel_data = await self._get_auction_page(page)
                if not parcel_data:
                    print(f"[Coconino] No parcels at page {page}, stopping", flush=True)
                    break

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
                        "billed_amount": face_amount,  # ✅ NOW FROM AUCTION PAGE
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
                    liens.append(lien)

                    # Enhanced logging
                    owner_str = details.get('owner_name', '?')[:30] if details.get('owner_name') else '?'
                    billed_str = f"${face_amount:,.2f}" if face_amount else "?"
                    value_str = f"${int(details.get('assessed_total_value'))}" if details.get('assessed_total_value') else "?"
                    print(f"[Coconino] {pid}: Billed={billed_str}, Owner={owner_str}, Value={value_str}", flush=True)

                    if limit > 0 and len(liens) >= limit:
                        print(f"[Coconino] Reached limit of {limit}", flush=True)
                        break

                if limit > 0 and len(liens) >= limit:
                    break

                await HumanBehavior.page_delay()
                page += 1

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
        """Get parcel details - Coconino Phase 1: Auction data only, assessor TBD"""
        # TODO: Implement assessor search integration for owner/property data
        # Currently returns minimal data - auction provides parcel ID only

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
            "owner_name": None,  # TODO: Add assessor search integration
            "owner_mailing_address": None,  # TODO: Add assessor search integration
        }

        return details

    def _parse_search_results(self, html: str, pid: str) -> dict:
        """Parse owner and property data from search results page"""
        data = {}

        # Owner Name - appears after account number in results
        # Example: "ANTELOPE HOSPITALITY LLC"
        owner_patterns = [
            r"R[0-9]{7,8}[A-Z]?\s*(?:<[^>]*>)*\s*([0-9-]+)\s+([A-Z][A-Z\s,&.'-]+?)(?:<br|287|[0-9]{3,5}\s+[A-Z])",
            r"Account#.*?<td[^>]*>([A-Z][A-Z\s,&.'-]{5,100}?)\s*(?:<br|[0-9])",
        ]
        for pattern in owner_patterns:
            match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
            if match:
                # Get the last captured group
                owner = match.group(match.lastindex).strip()
                if len(owner) > 3 and owner.upper() == owner:  # All caps indicates owner name
                    data["owner_name"] = owner
                    break

        # Owner Mailing Address - appears after owner name
        # Example: "287 N LAKE POWELL BLVD\nPAGE 86040"
        address_patterns = [
            r"([0-9]{3,5}\s+[A-Z\s]+(?:BLVD|ST|AVE|DR|RD|WAY|LN|CT|PL|CIR)[^\n<]{0,50})\s*(?:<br|<\/td|\n)\s*([A-Z\s]+\s+[0-9]{5})",
            r"<br\s*/>\s*([0-9]{3,5}[^<]{10,100}?)<br",
        ]
        for pattern in address_patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                if match.lastindex == 2:
                    # Address has two parts (street + city/zip)
                    street = match.group(1).strip()
                    city_zip = match.group(2).strip()
                    data["owner_mailing_address"] = f"{street}, {city_zip}"
                else:
                    data["owner_mailing_address"] = match.group(1).strip()
                break

        # Try simpler pattern if above didn't work
        if not data.get("owner_mailing_address"):
            # Look for any address-like pattern after owner name
            simple_addr = re.search(r"([0-9]{3,5}\s+[^\n<]{10,80})", html)
            if simple_addr:
                data["owner_mailing_address"] = simple_addr.group(1).strip()

        return data

    def _parse_base_document(self, html: str, pid: str) -> dict:
        """Parse basic property details from main assessor page"""
        data = {}

        # Legal Class
        match = re.search(r"Legal Class.*?<td[^>]*>([^<]+)</td>", html, re.DOTALL | re.IGNORECASE)
        if match:
            data["legal_class"] = match.group(1).strip()

        # Full Address
        address_patterns = [
            r"(?:Situs|Property|Physical)\s+(?:Address|Location)[:\s]+([^<\n]+)",
            r"<td[^>]*>\s*(?:Situs|Property)\s*Address[^<]*</td>\s*<td[^>]*>([^<]+)",
        ]
        for pattern in address_patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                addr = match.group(1).strip()
                if addr and len(addr) > 5:
                    data["full_address"] = addr
                    break

        # GIS Coordinates
        coord_patterns = [
            (r"latitude[\"']?\s*[:=]\s*([0-9.-]+)", r"longitude[\"']?\s*[:=]\s*([0-9.-]+)"),
            (r"lat[\"']?\s*[:=]\s*([0-9.-]+)", r"lng[\"']?\s*[:=]\s*([0-9.-]+)"),
        ]
        for lat_pattern, lng_pattern in coord_patterns:
            lat_match = re.search(lat_pattern, html, re.IGNORECASE)
            lng_match = re.search(lng_pattern, html, re.IGNORECASE)
            if lat_match and lng_match:
                try:
                    lat = float(lat_match.group(1))
                    lon = float(lng_match.group(1))
                    if 34 <= lat <= 37 and -115 <= lon <= -109:  # Arizona bounds
                        data["latitude"] = lat
                        data["longitude"] = lon
                        break
                except ValueError:
                    pass

        # Lot Size (Acres)
        lot_patterns = [
            r"(?:Lot Size|Acreage|Area)[:\s]+([0-9.]+)\s*(?:acres?|ac)",
            r"([0-9.]+)\s*(?:acres?|ac)",
        ]
        for pattern in lot_patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                try:
                    acres = float(match.group(1))
                    if 0.01 <= acres <= 10000:
                        data["lot_size_acres"] = acres
                        data["lot_size_sqft"] = int(acres * 43560)
                        break
                except ValueError:
                    pass

        # Zoning
        zoning_patterns = [
            r"(?:Zoning|Zone)[:\s]+([A-Z0-9-]+)",
            r"<td[^>]*>\s*Zoning[^<]*</td>\s*<td[^>]*>([^<]+)",
        ]
        for pattern in zoning_patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                data["zoning_code"] = match.group(1).strip()
                zoning_map = {
                    "R-1": "Single Family Residential",
                    "R-2": "Multi-Family Residential",
                    "C-1": "Commercial",
                    "A-1": "Agricultural",
                    "RU": "Rural Residential",
                }
                data["zoning_description"] = zoning_map.get(data["zoning_code"], "See County Zoning")
                break

        # Assessed Values
        value_patterns = [
            (r"(?:Land|Site)\s+Value[:\s]+\$?\s*([\d,]+)", "assessed_land_value"),
            (r"Improvement\s+Value[:\s]+\$?\s*([\d,]+)", "assessed_improvement_value"),
            (r"Total\s+(?:Assessed\s+)?Value[:\s]+\$?\s*([\d,]+)", "assessed_total_value"),
        ]
        for pattern, field in value_patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                try:
                    data[field] = float(match.group(1).replace(",", ""))
                except ValueError:
                    pass

        # Legal Description
        legal_patterns = [
            r"Legal Description[:\s]+([^<\n]{10,500})",
            r"<td[^>]*>\s*Legal[^<]*</td>\s*<td[^>]*>([^<]{10,500})",
        ]
        for pattern in legal_patterns:
            match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
            if match:
                desc = match.group(1).strip()
                if len(desc) > 10:
                    data["legal_description"] = desc[:1000]
                    break

        return data

    async def _get_owner_info(self, pid: str, doc_id: str) -> dict:
        """Fetch and parse ownership document"""
        url = f"{self.ASSESSOR_URL}/account.jsp?accountNum={pid}&doc={doc_id}"
        response = await self.session.get(url, cookies=self.assessor_cookies, headers=HumanBehavior.get_headers(), follow_redirects=True)

        owner_data = {
            "owner_name": None,
            "owner_mailing_address": None,
        }

        # Owner Name patterns
        name_patterns = [
            r"Owner\s+Name[:\s]+([^\n<]+)",
            r"<td[^>]*>\s*Owner\s*Name[^<]*</td>\s*<td[^>]*>([^<]+)",
            r"Name[:\s]+([A-Z][^\n<]{5,100})",
        ]
        for pattern in name_patterns:
            match = re.search(pattern, response.text, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                if len(name) > 3:  # Reasonable name length
                    owner_data["owner_name"] = name
                    break

        # Mailing Address patterns
        address_patterns = [
            r"Mailing\s+Address[:\s]+([^\n<]{10,200})",
            r"Owner\s+Address[:\s]+([^\n<]{10,200})",
            r"<td[^>]*>\s*Mailing\s*Address[^<]*</td>\s*<td[^>]*>([^<]{10,200})",
        ]
        for pattern in address_patterns:
            match = re.search(pattern, response.text, re.IGNORECASE)
            if match:
                addr = match.group(1).strip()
                if len(addr) > 10:
                    owner_data["owner_mailing_address"] = addr
                    break

        return owner_data

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
