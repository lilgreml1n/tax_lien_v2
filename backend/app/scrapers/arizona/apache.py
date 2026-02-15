"""
Apache County, Arizona Scraper

Sources:
- Auction listings: https://apache.arizonataxsale.com
- Treasurer (billed amounts): https://eagletreasurer.co.apache.az.us
- Assessor (legal class): https://eagleassessor.co.apache.az.us
"""
import re
import httpx
from typing import List, Dict, Any
from app.scrapers.base import CountyScraper, HumanBehavior


class ApacheScraper(CountyScraper):

    AUCTION_URL = "https://apache.arizonataxsale.com/index.cfm?folder=previewitems"
    TREASURER_URL = "https://eagletreasurer.co.apache.az.us:8443/treasurer/treasurerweb"
    ASSESSOR_URL = "https://eagleassessor.co.apache.az.us/assessor/taxweb"

    def __init__(self, state: str, county: str):
        super().__init__(state, county)
        self.treasurer_cookies = None
        self.assessor_cookies = None

    async def scrape(self, limit: int = 0) -> List[Dict[str, Any]]:
        liens = []
        try:
            await self._login_treasurer()
            await self._login_assessor()

            page = 1
            max_pages = 195

            while page <= max_pages:
                print(f"[Apache] Fetching page {page}...", flush=True)

                parcel_ids = await self._get_auction_page(page)
                if not parcel_ids:
                    print(f"[Apache] No parcels at page {page}, stopping", flush=True)
                    break

                for pid in parcel_ids:
                    await HumanBehavior.request_delay()

                    billed = await self._get_total_billed(pid)
                    details = await self._get_parcel_details(pid)

                    # Build URLs
                    assessor_url = f"{self.ASSESSOR_URL}/account.jsp?accountNum={pid}"
                    treasurer_url = f"{self.TREASURER_URL}/account.jsp?account={pid}"

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
                        "address": "Apache County, AZ",  # Keep for backward compatibility
                        "billed_amount": billed,
                        "state": "Arizona",
                        "county": "Apache",
                        # Merge all details
                        **details,
                        # URLs
                        "google_maps_url": google_maps_url,
                        "street_view_url": street_view_url,
                        "assessor_url": assessor_url,
                        "treasurer_url": treasurer_url,
                        "zillow_url": zillow_url,
                        "realtor_url": realtor_url,
                    }
                    liens.append(lien)

                    # Enhanced logging
                    acres_str = f"{details.get('lot_size_acres')}ac" if details.get('lot_size_acres') else "?"
                    value_str = f"${int(details.get('assessed_total_value'))}" if details.get('assessed_total_value') else "?"
                    print(f"[Apache] {pid}: ${billed:.2f}, {acres_str}, Value={value_str}, Zone={details.get('zoning_code', '?')}", flush=True)

                    if limit > 0 and len(liens) >= limit:
                        print(f"[Apache] Reached limit of {limit}", flush=True)
                        break

                if limit > 0 and len(liens) >= limit:
                    break

                await HumanBehavior.page_delay()
                page += 1

            print(f"[Apache] Scraped {len(liens)} total", flush=True)
        except Exception as e:
            print(f"[Apache] Error: {e}", flush=True)
            raise
        finally:
            await self.close()

        return liens

    async def _login_treasurer(self):
        print("[Apache] Logging into Treasurer...", flush=True)
        if not self.session:
            self.session = httpx.AsyncClient(timeout=30.0, verify=False)
        headers = HumanBehavior.get_headers()
        response = await self.session.post(
            f"{self.TREASURER_URL}/loginPOST.jsp",
            data={"submit": "Login", "guest": "true"},
            headers=headers,
            follow_redirects=True,
        )
        self.treasurer_cookies = response.cookies

    async def _login_assessor(self):
        print("[Apache] Logging into Assessor...", flush=True)
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

    async def _get_auction_page(self, page_num: int) -> List[str]:
        if not self.session:
            self.session = httpx.AsyncClient(timeout=30.0, verify=False)
        headers = HumanBehavior.get_headers()
        response = await self.session.post(
            self.AUCTION_URL,
            data={"pageNum": str(page_num)},
            headers=headers,
            follow_redirects=True,
        )
        parcel_ids = re.findall(r"account=([A-Z0-9]+)", response.text)
        if not parcel_ids:
            response = await self.session.get(
                f"{self.AUCTION_URL}&pageNum={page_num}",
                headers=headers,
                follow_redirects=True,
            )
            parcel_ids = re.findall(r"account=([A-Z0-9]+)", response.text)
        return list(set(parcel_ids))

    async def _get_total_billed(self, pid: str) -> float:
        if not self.session:
            self.session = httpx.AsyncClient(timeout=30.0, verify=False)
        url = f"{self.TREASURER_URL}/account.jsp?account={pid}"
        response = await self.session.get(url, cookies=self.treasurer_cookies, headers=HumanBehavior.get_headers(), follow_redirects=True)
        match = re.search(r"Total Billed.*?\$\s*([\d,.]+)", response.text, re.DOTALL | re.IGNORECASE)
        if match:
            try:
                return float(match.group(1).replace(",", ""))
            except ValueError:
                return 0.0
        return 0.0

    async def _get_legal_class(self, pid: str) -> str:
        """Legacy method - use _get_parcel_details instead"""
        if not self.session:
            self.session = httpx.AsyncClient(timeout=30.0, verify=False)
        url = f"{self.ASSESSOR_URL}/account.jsp?accountNum={pid}"
        response = await self.session.get(url, cookies=self.assessor_cookies, headers=HumanBehavior.get_headers(), follow_redirects=True)
        match = re.search(r"Legal Class.*?<td[^>]*>([^<]+)</td>", response.text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return "Unknown"

    async def _get_parcel_details(self, pid: str) -> dict:
        """Get all parcel details from Assessor page - Phase 1A enhanced"""
        if not self.session:
            self.session = httpx.AsyncClient(timeout=30.0, verify=False)

        url = f"{self.ASSESSOR_URL}/account.jsp?accountNum={pid}"
        response = await self.session.get(url, cookies=self.assessor_cookies, headers=HumanBehavior.get_headers(), follow_redirects=True)

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

        # Legal Class
        match = re.search(r"Legal Class.*?<td[^>]*>([^<]+)</td>", response.text, re.DOTALL | re.IGNORECASE)
        if match:
            details["legal_class"] = match.group(1).strip()

        # Full Address
        address_patterns = [
            r"(?:Situs|Property|Physical)\s+(?:Address|Location)[:\s]+([^<\n]+)",
            r"<td[^>]*>\s*(?:Situs|Property)\s*Address[^<]*</td>\s*<td[^>]*>([^<]+)",
        ]
        for pattern in address_patterns:
            match = re.search(pattern, response.text, re.IGNORECASE)
            if match:
                addr = match.group(1).strip()
                if addr and len(addr) > 5:
                    details["full_address"] = addr
                    break

        # GIS Coordinates
        coord_patterns = [
            (r"latitude[\"']?\s*[:=]\s*([0-9.-]+)", r"longitude[\"']?\s*[:=]\s*([0-9.-]+)"),
            (r"lat[\"']?\s*[:=]\s*([0-9.-]+)", r"lng[\"']?\s*[:=]\s*([0-9.-]+)"),
        ]
        for lat_pattern, lng_pattern in coord_patterns:
            lat_match = re.search(lat_pattern, response.text, re.IGNORECASE)
            lng_match = re.search(lng_pattern, response.text, re.IGNORECASE)
            if lat_match and lng_match:
                try:
                    lat = float(lat_match.group(1))
                    lon = float(lng_match.group(1))
                    if 31 <= lat <= 37 and -115 <= lon <= -109:
                        details["latitude"] = lat
                        details["longitude"] = lon
                        break
                except ValueError:
                    pass

        # Lot Size (Acres and Sqft)
        lot_patterns = [
            r"(?:Lot Size|Acreage|Area)[:\s]+([0-9.]+)\s*(?:acres?|ac)",
            r"([0-9.]+)\s*(?:acres?|ac)",
        ]
        for pattern in lot_patterns:
            match = re.search(pattern, response.text, re.IGNORECASE)
            if match:
                try:
                    acres = float(match.group(1))
                    if 0.01 <= acres <= 10000:  # Reasonable range
                        details["lot_size_acres"] = acres
                        details["lot_size_sqft"] = int(acres * 43560)
                        break
                except ValueError:
                    pass

        # If no acres found, try sqft
        if not details["lot_size_sqft"]:
            sqft_patterns = [
                r"([0-9,]+)\s*(?:sq\.?\s*ft|square feet|sqft)",
            ]
            for pattern in sqft_patterns:
                match = re.search(pattern, response.text, re.IGNORECASE)
                if match:
                    try:
                        sqft = int(match.group(1).replace(",", ""))
                        if 100 <= sqft <= 500000000:
                            details["lot_size_sqft"] = sqft
                            details["lot_size_acres"] = round(sqft / 43560, 2)
                            break
                    except ValueError:
                        pass

        # Zoning
        zoning_patterns = [
            r"(?:Zoning|Zone)[:\s]+([A-Z0-9-]+)",
            r"<td[^>]*>\s*Zoning[^<]*</td>\s*<td[^>]*>([^<]+)",
        ]
        for pattern in zoning_patterns:
            match = re.search(pattern, response.text, re.IGNORECASE)
            if match:
                details["zoning_code"] = match.group(1).strip()
                # Common zoning descriptions
                zoning_map = {
                    "R-1": "Single Family Residential",
                    "R-2": "Multi-Family Residential",
                    "C-1": "Commercial",
                    "A-1": "Agricultural",
                    "RU": "Rural Residential",
                }
                details["zoning_description"] = zoning_map.get(details["zoning_code"], "See County Zoning")
                break

        # Assessed Values
        value_patterns = [
            (r"(?:Land|Site)\s+Value[:\s]+\$?\s*([\d,]+)", "assessed_land_value"),
            (r"Improvement\s+Value[:\s]+\$?\s*([\d,]+)", "assessed_improvement_value"),
            (r"Total\s+(?:Assessed\s+)?Value[:\s]+\$?\s*([\d,]+)", "assessed_total_value"),
        ]
        for pattern, field in value_patterns:
            match = re.search(pattern, response.text, re.IGNORECASE)
            if match:
                try:
                    details[field] = float(match.group(1).replace(",", ""))
                except ValueError:
                    pass

        # Legal Description
        legal_patterns = [
            r"Legal Description[:\s]+([^<\n]{10,500})",
            r"<td[^>]*>\s*Legal[^<]*</td>\s*<td[^>]*>([^<]{10,500})",
        ]
        for pattern in legal_patterns:
            match = re.search(pattern, response.text, re.IGNORECASE | re.DOTALL)
            if match:
                desc = match.group(1).strip()
                if len(desc) > 10:
                    details["legal_description"] = desc[:1000]  # Cap at 1000 chars
                    break

        # Owner Name
        owner_patterns = [
            r"(?:Owner|Taxpayer)\s*Name[:\s]+([^<\n]{2,200})",
            r"<td[^>]*>\s*(?:Owner|Taxpayer)[^<]*</td>\s*<td[^>]*>([^<]{2,200})",
            r"(?:Owner|Taxpayer)[:\s]*<[^>]*>([^<]{2,200})",
        ]
        for pattern in owner_patterns:
            match = re.search(pattern, response.text, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                if len(name) > 2 and not name.lower().startswith("owner"):
                    details["owner_name"] = name[:255]
                    break

        # Owner Mailing Address
        mailing_patterns = [
            r"(?:Mailing|Tax)\s+Address[:\s]+([^<\n]{5,500})",
            r"<td[^>]*>\s*(?:Mailing|Tax)\s+Address[^<]*</td>\s*<td[^>]*>([^<]{5,500})",
        ]
        for pattern in mailing_patterns:
            match = re.search(pattern, response.text, re.IGNORECASE | re.DOTALL)
            if match:
                addr = match.group(1).strip()
                # Clean up extra whitespace and newlines
                addr = re.sub(r'\s+', ' ', addr)
                if len(addr) > 5:
                    details["owner_mailing_address"] = addr[:500]
                    break

        return details

    def _build_google_maps_url(self, lat: float = None, lon: float = None, address: str = None, parcel_id: str = None) -> str:
        """Build Google Maps URL from coordinates or address"""
        if lat and lon:
            # Prefer coordinates if available
            return f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
        elif address:
            # Use address search
            import urllib.parse
            encoded_address = urllib.parse.quote(address)
            return f"https://www.google.com/maps/search/?api=1&query={encoded_address}"
        elif parcel_id:
            # Fallback: search for parcel in Apache County
            return f"https://www.google.com/maps/search/?api=1&query=Parcel+{parcel_id}+Apache+County+Arizona"
        else:
            # Last resort: just Apache County
            return "https://www.google.com/maps/search/?api=1&query=Apache+County+Arizona"

    def _build_street_view_url(self, lat: float = None, lon: float = None, address: str = None) -> str:
        """Build Google Street View URL (clickable link, no API call)"""
        if lat and lon:
            # Street View at coordinates
            return f"https://www.google.com/maps/@{lat},{lon},3a,75y,0h,90t/data=!3m6!1e1!3m4!1s0!2e0!7i13312!8i6656"
        elif address:
            # Street View search by address
            import urllib.parse
            encoded = urllib.parse.quote(address)
            return f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=&pano={encoded}"
        else:
            return None

    def _build_zillow_url(self, address: str = None, parcel_id: str = None) -> str:
        """Build Zillow property page URL (clickable link, no API call)"""
        if address:
            import urllib.parse
            # Zillow search URL
            encoded = urllib.parse.quote(address)
            return f"https://www.zillow.com/homes/{encoded}_rb/"
        elif parcel_id:
            # Search by parcel ID
            return f"https://www.zillow.com/homes/Parcel-{parcel_id}-Apache-County-AZ_rb/"
        else:
            return None

    def _build_realtor_url(self, address: str = None, parcel_id: str = None) -> str:
        """Build Realtor.com property page URL (clickable link, no API call)"""
        if address:
            import urllib.parse
            # Realtor.com search URL
            encoded = urllib.parse.quote(address)
            return f"https://www.realtor.com/realestateandhomes-search/{encoded}"
        elif parcel_id:
            # Search by parcel + location
            return f"https://www.realtor.com/realestateandhomes-search/Apache-County_AZ/parcel-{parcel_id}"
        else:
            return None
