"""
Apache County, Arizona Scraper

Sources:
- Auction listings: https://apache.arizonataxsale.com
- Treasurer (billed amounts): https://eagletreasurer.co.apache.az.us
- Assessor (owner/value/lot): https://eagleassessor.co.apache.az.us
- GIS centroids: https://services8.arcgis.com (public, no auth)
"""
import re
import httpx
from typing import List, Dict, Any, Callable, Optional
from app.scrapers.base import CountyScraper, HumanBehavior, with_retry


class ApacheScraper(CountyScraper):

    AUCTION_URL = "https://apache.arizonataxsale.com/index.cfm?folder=previewitems"
    TREASURER_URL = "https://eagletreasurer.co.apache.az.us:8443/treasurer/treasurerweb"
    ASSESSOR_URL = "https://eagleassessor.co.apache.az.us/assessor/taxweb"
    GIS_URL = "https://services8.arcgis.com/KyZIQDOsXnGaTxj2/arcgis/rest/services/Parcels/FeatureServer/0/query"
    ESRI_GEOCODE_URL = "https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/reverseGeocode"

    def __init__(self, state: str, county: str):
        super().__init__(state, county)
        self.treasurer_cookies = None
        self.assessor_cookies = None

    async def scrape(self, limit: int = 0, start_page: int = 1,
                     on_page_complete: Optional[Callable] = None) -> List[Dict[str, Any]]:
        liens = []
        total_scraped = 0
        try:
            await self._login_treasurer()
            await self._login_assessor()

            page = start_page
            max_pages = 195

            if start_page > 1:
                print(f"[Apache] Resuming from page {start_page}", flush=True)

            while page <= max_pages:
                print(f"[Apache] Fetching page {page}...", flush=True)

                parcel_ids = await with_retry(
                    lambda: self._get_auction_page(page),
                    label=f"Apache auction page {page}",
                    max_wait=300,
                    retry_delay=30,
                )
                if not parcel_ids:
                    print(f"[Apache] No parcels at page {page}, stopping", flush=True)
                    break

                page_liens = []
                for pid in parcel_ids:
                    await HumanBehavior.request_delay()

                    try:
                        billed = await with_retry(
                            lambda: self._get_total_billed(pid),
                            label=f"Apache treasurer {pid}",
                            max_wait=300,
                            retry_delay=30,
                        )
                    except Exception as e:
                        print(f"[Apache] {pid}: Failed to get billed amount - {e}", flush=True)
                        billed = None

                    try:
                        details = await with_retry(
                            lambda: self._get_parcel_details(pid),
                            label=f"Apache assessor {pid}",
                            max_wait=300,
                            retry_delay=30,
                        )
                    except Exception as e:
                        print(f"[Apache] {pid}: Failed to get parcel details - {e}", flush=True)
                        details = {}

                    try:
                        await HumanBehavior.request_delay()
                        tax_history = await with_retry(
                            lambda: self._get_tax_history(pid),
                            label=f"Apache tax history {pid}",
                            max_wait=60,
                            retry_delay=10,
                        )
                        details.update(tax_history)
                    except Exception as e:
                        print(f"[Apache] {pid}: Failed to get tax history - {e}", flush=True)

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
                    page_liens.append(lien)
                    total_scraped += 1

                    # Enhanced logging with fallbacks for missing data
                    acres_str = f"{details.get('lot_size_acres')}ac" if details.get('lot_size_acres') else "?"
                    value_str = f"${int(details.get('assessed_total_value'))}" if details.get('assessed_total_value') else "?"
                    billed_str = f"${billed:.2f}" if billed else "NULL"
                    print(f"[Apache] {pid}: {billed_str}, {acres_str}, Value={value_str}, Zone={details.get('zoning_code', '?')}", flush=True)

                    if limit > 0 and total_scraped >= limit:
                        print(f"[Apache] Reached limit of {limit}", flush=True)
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

    async def _get_tax_history(self, pid: str) -> dict:
        """
        Fetch tax payment history from treasurer &action=tx page.

        Returns summary metrics for Capital Guardian:
          - years_delinquent: consecutive years with any amount outstanding
          - prior_liens_count: years where Lien Due > 0 (other investors hold liens)
          - total_outstanding: sum of all Total Due across all years
          - first_delinquent_year: earliest year with any amount due

        HTML: <h2>Summary</h2><table class='account'>
        Columns: Tax Due | Interest Due | Penalty Due | Misc Due | Lien Due | Lien Interest Due | Total Due
        """
        if not self.session:
            self.session = httpx.AsyncClient(timeout=30.0, verify=False)

        url = f"{self.TREASURER_URL}/account.jsp?account={pid}&action=tx"
        response = await self.session.get(url, cookies=self.treasurer_cookies,
                                          headers=HumanBehavior.get_headers(), follow_redirects=True)
        html = response.text

        result = {
            "years_delinquent": None,
            "prior_liens_count": None,
            "total_outstanding": None,
            "first_delinquent_year": None,
        }

        m = re.search(r'<h2>Summary</h2>(.*?)</table>', html, re.DOTALL)
        if not m:
            return result

        table = m.group(1)
        rows = re.findall(r'<tr><td>(\d{4})</td>(.*?)</tr>', table, re.DOTALL)
        if not rows:
            return result

        year_data = []
        for year_str, cells in rows:
            vals = re.findall(r'\$([0-9,.]+)', cells)
            if len(vals) >= 7:
                try:
                    year_data.append({
                        "year": int(year_str),
                        "tax_due": float(vals[0].replace(",", "")),
                        "lien_due": float(vals[4].replace(",", "")),
                        "total_due": float(vals[6].replace(",", "")),
                    })
                except (ValueError, IndexError):
                    pass

        if not year_data:
            return result

        total_outstanding = sum(r["total_due"] for r in year_data)
        prior_liens_count = sum(1 for r in year_data if r["lien_due"] > 0)
        delinquent_years = [r["year"] for r in year_data if r["total_due"] > 0]
        first_delinquent_year = min(delinquent_years) if delinquent_years else None

        # Consecutive delinquent years counting backward from current
        sorted_years = sorted(delinquent_years, reverse=True)
        consecutive = 0
        for i, yr in enumerate(sorted_years):
            if i == 0 or sorted_years[i - 1] - yr == 1:
                consecutive += 1
            else:
                break

        result["years_delinquent"] = consecutive
        result["prior_liens_count"] = prior_liens_count
        result["total_outstanding"] = round(total_outstanding, 2)
        result["first_delinquent_year"] = first_delinquent_year
        return result

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
        """Get all parcel details from Assessor pages.

        Fetches TWO documents:
        1. Summary page - owner, address, FCV, legal class, legal description
        2. Parcel Detail sub-doc - lot size (not available on summary page)

        HTML structure verified against real Apache assessor responses 2026-02-17.
        See APACHE_COUNTY_GOTCHAS.md section 4 for detailed pattern notes.
        """
        if not self.session:
            self.session = httpx.AsyncClient(timeout=30.0, verify=False)

        url = f"{self.ASSESSOR_URL}/account.jsp?accountNum={pid}"
        response = await self.session.get(url, cookies=self.assessor_cookies, headers=HumanBehavior.get_headers(), follow_redirects=True)
        html = response.text

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

        # --- Legal Class ---
        # Pattern: <b>Legal Class</b> in <th>, then <td align="left">02.R</td>
        match = re.search(r"Legal Class.*?<td[^>]*>([^<]+)</td>", html, re.DOTALL | re.IGNORECASE)
        if match:
            details["legal_class"] = match.group(1).strip()

        # --- Situs Address (often empty for vacant land) ---
        match = re.search(r"<strong>Situs\s+Address</strong>\s*([^<]*)", html)
        if match:
            addr = match.group(1).strip()
            if len(addr) > 3:
                details["full_address"] = addr

        # --- Owner Name ---
        # Format: <b>Owner Name</b> 2 GUYS INVESTMENTS LLC  (inline, not a table cell)
        match = re.search(r"<b>Owner\s+Name</b>\s*([^\n<]+)", html)
        if match:
            name = match.group(1).strip()
            if len(name) > 2:
                details["owner_name"] = name[:255]

        # --- Owner Mailing Address ---
        # Format: <b>Owner Address</b> PO BOX 265 <br>SNOWFLAKE, AZ 85937
        match = re.search(r"<b>Owner\s+Address</b>\s*((?:[^<]|<br[^>]*>)+)", html)
        if match:
            raw = match.group(1)
            addr = re.sub(r"<br[^>]*>", " ", raw).strip()
            addr = re.sub(r"\s+", " ", addr)
            if len(addr) > 5:
                details["owner_mailing_address"] = addr[:500]

        # --- Full Cash Value (FCV) → assessed_total_value ---
        # Label is "Full Cash Value (FCV)", NOT "Total Value"
        # Format: <b>Full Cash Value (FCV)</b><td align="right">$5,900
        match = re.search(r"Full Cash Value \(FCV\)</b><td[^>]*>\$?([\d,]+)", html)
        if match:
            try:
                details["assessed_total_value"] = float(match.group(1).replace(",", ""))
            except ValueError:
                pass

        # --- Legal Description ---
        # Format: after "Legal Summary" heading with nested <font> tag and closing </strong>
        # Example: <strong>Legal Summary <font ...>...</font></strong> Subdivision: ...
        match = re.search(r"Legal Summary[^<]*(?:<[^>]+>)*</strong>\s*([^<]+)", html)
        if match:
            desc = re.sub(r"\s+", " ", match.group(1).strip())
            if len(desc) > 5:
                details["legal_description"] = desc[:1000]

        # --- Lot Size: requires second fetch to Parcel Detail sub-document ---
        # The doc ID is embedded in the sidebar nav link:
        # <a ... href="account.jsp?accountNum=R0026183&doc=R0026183.1721088546772">Parcel Detail</a>
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

                # Parcel Size value
                size_match = re.search(
                    r"Parcel Size</span><br[^/]*/><span[^>]*><span[^>]*>([\d.]+)", detail_html
                )
                # Unit of Measure (Acre / Sq Ft)
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
                    # No unit — assume acres if reasonable
                    size_val = float(size_match.group(1))
                    if 0.001 <= size_val <= 10000:
                        details["lot_size_acres"] = size_val
                        details["lot_size_sqft"] = int(size_val * 43560)
            except Exception as e:
                print(f"[Apache] {pid}: Parcel Detail sub-doc failed - {e}", flush=True)

        # --- GIS Centroid (ArcGIS REST API, public, no auth) ---
        try:
            gis = await self._get_gis_data(pid)
            if gis:
                details["latitude"] = gis.get("lat")
                details["longitude"] = gis.get("lon")
                # Use situs from GIS if assessor page had no address
                if not details["full_address"] and gis.get("situs"):
                    details["full_address"] = gis["situs"]
        except Exception as e:
            print(f"[Apache] {pid}: GIS lookup failed - {e}", flush=True)

        return details

    async def _get_gis_data(self, account_number: str) -> Optional[dict]:
        """
        Fetch parcel centroid from Apache County ArcGIS REST API.
        Public service, no authentication required.
        Returns: {lat, lon, situs, parcel_num} or None
        """
        params = {
            "where": f"ACCOUNTNUMBER='{account_number}'",
            "outFields": "ACCOUNTNUMBER,PARCEL_NUM,OWNERNAME,SITUS",
            "returnGeometry": "true",
            "returnCentroid": "true",
            "outSR": "4326",
            "f": "json",
        }
        resp = await self.session.get(self.GIS_URL, params=params, timeout=15)
        data = resp.json()
        features = data.get("features", [])
        if not features:
            return None

        feat = features[0]
        centroid = feat.get("centroid") or {}

        # Fallback: compute centroid from polygon rings
        if not centroid and feat.get("geometry", {}).get("rings"):
            rings = feat["geometry"]["rings"][0]
            lons = [p[0] for p in rings]
            lats = [p[1] for p in rings]
            centroid = {"x": sum(lons) / len(lons), "y": sum(lats) / len(lats)}

        lat = centroid.get("y")
        lon = centroid.get("x")

        # Validate Arizona bounds
        if lat and lon and not (31 <= lat <= 37 and -115 <= lon <= -109):
            lat, lon = None, None

        situs = (feat["attributes"].get("SITUS") or "").strip() or None

        # Reverse geocode if no SITUS address and we have valid coordinates
        if not situs and lat and lon:
            try:
                geo_resp = await self.session.get(self.ESRI_GEOCODE_URL, params={
                    "location": f"{lon},{lat}", "f": "json",
                }, timeout=10)
                match_addr = geo_resp.json().get("address", {}).get("Match_addr")
                if match_addr:
                    situs = match_addr
            except Exception:
                pass

        return {
            "lat": lat,
            "lon": lon,
            "situs": situs,
            "parcel_num": feat["attributes"].get("PARCEL_NUM"),
        }

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
