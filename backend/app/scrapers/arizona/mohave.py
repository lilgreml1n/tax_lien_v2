"""
Mohave County, Arizona Scraper

Sources:
- Auction list: https://resources.mohavecounty.us/file/Treasurer/TaxLienSale/TaxSaleList.xlsx
  (Excel file, Cloudflare-protected → requires Playwright browser download)
- EagleWeb (treasurer): https://eagletw.mohavecounty.us/treasurer/treasurerweb
  (Tyler Technologies EagleWeb — owner, values, tax history)
- GIS: https://mcgis.mohave.gov/arcgis/rest/services/Mohave/MapServer/38/query
  (Public ArcGIS REST — lat/lon, lot size, land/imp values, use code)
  Query key: ACCOUNTNO = 'R' + parcel_number (e.g. parcel 10134003 → R10134003)

Architecture difference vs Apache:
  Apache: scrape HTML auction pages → assessor per parcel → treasurer per parcel
  Mohave: download Excel once → EagleWeb per parcel + GIS per parcel

Parcel ID format: R0000332 (letter R + 7 digits, EagleWeb account number)
Checkpoint "page": every CHECKPOINT_SIZE rows of the Excel = one checkpoint page
"""
import re
import io
import asyncio
import random
import tempfile
import os
from typing import List, Dict, Any, Callable, Optional

import httpx

from app.scrapers.base import CountyScraper, HumanBehavior, with_retry

CHECKPOINT_SIZE = 10   # parcels per checkpoint save (resume granularity)
PAGE_DELAY_EVERY = 50  # parcels between human-like page delays


class MohaveScraper(CountyScraper):

    EXCEL_URL = "https://resources.mohavecounty.us/file/Treasurer/TaxLienSale/TaxSaleList.xlsx"
    TREASURER_URL = "https://eagletw.mohavecounty.us/treasurer/treasurerweb"
    GIS_URL = "https://mcgis.mohave.gov/arcgis/rest/services/Mohave/MapServer/38/query"

    def __init__(self, state: str, county: str):
        super().__init__(state, county)
        self.treasurer_cookies = None

    async def scrape(self, limit: int = 0, start_page: int = 1,
                     on_page_complete: Optional[Callable] = None) -> List[Dict[str, Any]]:
        """
        Phase 1 scrape for Mohave County.

        start_page maps to row offset in Excel:
          page 1 → start at row 0
          page 2 → start at row BATCH_SIZE
          etc.
        """
        all_liens = []

        try:
            # Step 1: Download and parse Excel
            print("[Mohave] Downloading Excel auction list via Playwright...", flush=True)
            excel_bytes = await self._download_excel_playwright()
            parcels_from_excel = self._parse_excel(excel_bytes)
            self.total_parcels_available = len(parcels_from_excel)  # Known upfront from Excel
            print(f"[Mohave] Found {len(parcels_from_excel)} parcels in Excel", flush=True)

            # Step 2: Login to EagleWeb as guest
            await self._login_treasurer()

            # Apply start_page offset (each "page" = CHECKPOINT_SIZE rows)
            start_row = (start_page - 1) * CHECKPOINT_SIZE
            if start_row > 0:
                print(f"[Mohave] Resuming from row {start_row} (page {start_page})", flush=True)

            parcels_to_process = parcels_from_excel[start_row:]
            if limit > 0:
                parcels_to_process = parcels_to_process[:limit]

            total_scraped = 0
            checkpoint_batch = []
            checkpoint_page = start_page

            for excel_row in parcels_to_process:
                await HumanBehavior.request_delay()

                r_number = excel_row["r_number"]

                parcel_number = excel_row.get("parcel_number", "")

                try:
                    details = await with_retry(
                        lambda r=r_number, p=parcel_number: self._get_eagleweb_details(r, parcel_number=p),
                        label=f"Mohave EagleWeb {r_number}",
                        max_wait=300,
                        retry_delay=30,
                    )
                except Exception as e:
                    print(f"[Mohave] {r_number}: EagleWeb failed - {e}", flush=True)
                    details = {}

                # Build review URLs
                treasurer_url = f"{self.TREASURER_URL}/account.jsp?account={r_number}"
                assessor_url = f"https://www.mohave.gov/departments/assessor/assessor-search/?parcel={parcel_number}"

                lat = details.get("latitude")
                lon = details.get("longitude")
                full_address = details.get("full_address")
                google_maps_url = self._build_google_maps_url(lat=lat, lon=lon, address=full_address, parcel_id=r_number)
                street_view_url = self._build_street_view_url(lat=lat, lon=lon, address=full_address)
                zillow_url = self._build_zillow_url(address=full_address, parcel_id=r_number)
                realtor_url = self._build_realtor_url(address=full_address, parcel_id=r_number)

                # Owner name: prefer Excel (more reliable), fall back to EagleWeb
                owner_name = excel_row.get("owner_name") or details.get("owner_name")

                lien = {
                    "parcel_id": r_number,
                    "address": "Mohave County, AZ",
                    "billed_amount": excel_row.get("billed_amount"),
                    "owner_name": owner_name,
                    "state": "Arizona",
                    "county": "Mohave",
                    # EagleWeb details (owner_name in details would override above if not None)
                    **{k: v for k, v in details.items() if k != "owner_name"},
                    # Restore owner_name after spread (Excel takes priority)
                    "owner_name": owner_name,
                    # URLs
                    "treasurer_url": treasurer_url,
                    "assessor_url": assessor_url,
                    "google_maps_url": google_maps_url,
                    "street_view_url": street_view_url,
                    "zillow_url": zillow_url,
                    "realtor_url": realtor_url,
                    "source_url": self.EXCEL_URL,
                    "auction_url": self.EXCEL_URL,
                }

                checkpoint_batch.append(lien)
                total_scraped += 1

                billed_str = f"${excel_row.get('billed_amount', 0):.2f}" if excel_row.get("billed_amount") else "NULL"
                print(f"[Mohave] {r_number}: {billed_str} | {(full_address or 'no address')[:50]}", flush=True)

                # Save checkpoint every CHECKPOINT_SIZE parcels
                if len(checkpoint_batch) >= CHECKPOINT_SIZE:
                    if on_page_complete:
                        on_page_complete(checkpoint_batch, checkpoint_page)
                    all_liens.extend(checkpoint_batch)
                    checkpoint_batch = []
                    checkpoint_page += 1

                # Human-like page delay every PAGE_DELAY_EVERY parcels
                if total_scraped % PAGE_DELAY_EVERY == 0:
                    await HumanBehavior.page_delay()

                if limit > 0 and total_scraped >= limit:
                    break

            # Flush any remaining
            if checkpoint_batch:
                if on_page_complete:
                    on_page_complete(checkpoint_batch, checkpoint_page)
                all_liens.extend(checkpoint_batch)

            print(f"[Mohave] Scraped {len(all_liens)} total", flush=True)

        except Exception as e:
            print(f"[Mohave] Error: {e}", flush=True)
            raise
        finally:
            await self.close()

        return all_liens

    async def _download_excel_playwright(self) -> bytes:
        """Download Excel from Cloudflare-protected URL using a Playwright browser session."""
        from playwright.async_api import async_playwright

        with tempfile.TemporaryDirectory() as tmp_dir:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
                )
                context = await browser.new_context(
                    user_agent=random.choice(HumanBehavior.USER_AGENTS),
                    accept_downloads=True,
                )
                page = await context.new_page()

                # Visit the main domain first to get past Cloudflare
                print("[Mohave] Visiting resources site to establish session...", flush=True)
                try:
                    await page.goto(
                        "https://resources.mohavecounty.us/",
                        wait_until="domcontentloaded",
                        timeout=30000,
                    )
                except Exception:
                    pass  # Redirect / timeout on root is OK
                await asyncio.sleep(random.uniform(2, 4))

                # Trigger the download
                # NOTE: goto() raises ERR_ABORTED for direct file download URLs — this is
                # expected and normal. The download is still captured by expect_download().
                download_path = os.path.join(tmp_dir, "tax_sale.xlsx")
                print(f"[Mohave] Initiating download from {self.EXCEL_URL}...", flush=True)
                async with page.expect_download(timeout=90000) as download_info:
                    try:
                        await page.goto(self.EXCEL_URL)
                    except Exception:
                        pass  # ERR_ABORTED is expected for file download URLs
                download = await download_info.value
                await download.save_as(download_path)
                await browser.close()

            with open(download_path, "rb") as f:
                content = f.read()

        print(f"[Mohave] Downloaded {len(content):,} bytes", flush=True)
        return content

    def _parse_excel(self, excel_bytes: bytes) -> List[Dict]:
        """Parse Excel to extract parcel list.

        Expected columns: Tax Sale Number | Account | Parcel Number | Owner Name | Amount Due
        Column order may vary — detection is case-insensitive keyword matching.
        """
        import openpyxl

        wb = openpyxl.load_workbook(io.BytesIO(excel_bytes), data_only=True)
        ws = wb.active

        parcels = []
        header = None

        for row in ws.iter_rows(values_only=True):
            # Detect header row by looking for known keywords
            if header is None:
                row_lower = [str(c).lower().strip() if c is not None else "" for c in row]
                if any("account" in c for c in row_lower):
                    header = row_lower
                continue

            if not any(row):
                continue

            row_dict = dict(zip(header, row))

            # Account (R-number)
            r_number = None
            for key in header:
                if "account" in key:
                    val = row_dict.get(key)
                    if val and str(val).strip().upper().startswith("R"):
                        r_number = str(val).strip().upper()
                        break
            if not r_number:
                continue

            # Parcel number (8-digit APN)
            parcel_number = None
            for key in header:
                if "parcel" in key:
                    val = row_dict.get(key)
                    if val:
                        parcel_number = str(val).strip()
                        break

            # Owner name
            owner_name = None
            for key in header:
                if "owner" in key:
                    val = row_dict.get(key)
                    if val:
                        owner_name = str(val).strip()[:255]
                        break

            # Amount due / billed amount
            billed_amount = None
            for key in header:
                if "amount" in key or "due" in key:
                    val = row_dict.get(key)
                    if val is not None:
                        try:
                            billed_amount = float(str(val).replace("$", "").replace(",", "").strip())
                        except (ValueError, AttributeError):
                            pass
                        break

            parcels.append({
                "r_number": r_number,
                "parcel_number": parcel_number,
                "owner_name": owner_name,
                "billed_amount": billed_amount,
            })

        return parcels

    async def _login_treasurer(self):
        print("[Mohave] Logging into EagleWeb as guest...", flush=True)
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

    async def _get_eagleweb_details(self, r_number: str, parcel_number: str = None) -> dict:
        """Fetch all parcel details from EagleWeb (3 pages) + GIS if parcel_number provided."""
        if not self.session:
            self.session = httpx.AsyncClient(timeout=30.0, verify=False)

        details = {
            "owner_name": None,
            "owner_mailing_address": None,
            "full_address": None,
            "legal_description": None,
            "legal_class": None,
            "assessed_total_value": None,
            "assessed_land_value": None,
            "assessed_improvement_value": None,
            "latitude": None,
            "longitude": None,
            "lot_size_acres": None,
            "lot_size_sqft": None,
            "zoning_code": None,
            "years_delinquent": None,
            "prior_liens_count": None,
            "total_outstanding": None,
            "first_delinquent_year": None,
        }

        # -- Summary page --
        try:
            url = f"{self.TREASURER_URL}/account.jsp?account={r_number}"
            resp = await self.session.get(
                url, cookies=self.treasurer_cookies,
                headers=HumanBehavior.get_headers(), follow_redirects=True,
            )
            summary = self._parse_summary(resp.text)
            details.update(summary)
        except Exception as e:
            print(f"[Mohave] {r_number}: Summary page failed - {e}", flush=True)

        await HumanBehavior.request_delay()

        # -- Billing page --
        try:
            url = f"{self.TREASURER_URL}/account.jsp?account={r_number}&action=billing"
            resp = await self.session.get(
                url, cookies=self.treasurer_cookies,
                headers=HumanBehavior.get_headers(), follow_redirects=True,
            )
            billing = self._parse_billing(resp.text)
            for k, v in billing.items():
                if v is not None:
                    details[k] = v
        except Exception as e:
            print(f"[Mohave] {r_number}: Billing page failed - {e}", flush=True)

        await HumanBehavior.request_delay()

        # -- Transaction history page --
        try:
            url = f"{self.TREASURER_URL}/account.jsp?account={r_number}&action=tx"
            resp = await self.session.get(
                url, cookies=self.treasurer_cookies,
                headers=HumanBehavior.get_headers(), follow_redirects=True,
            )
            tx = self._parse_tx_history(resp.text)
            for k, v in tx.items():
                if v is not None:
                    details[k] = v
        except Exception as e:
            print(f"[Mohave] {r_number}: TX page failed - {e}", flush=True)

        # -- GIS lookup (lat/lon, lot size, land/imp values, use code) --
        if parcel_number:
            try:
                await HumanBehavior.request_delay()
                gis = await self._get_gis_data(parcel_number)
                if gis:
                    for k, v in gis.items():
                        if v is not None:
                            details[k] = v
            except Exception as e:
                print(f"[Mohave] {r_number}: GIS lookup failed - {e}", flush=True)

        return details

    async def _get_gis_data(self, parcel_number: str) -> Optional[dict]:
        """
        Fetch parcel data from Mohave County public ArcGIS REST service.
        Query key: ACCOUNTNO = 'R' + parcel_number (e.g. 10134003 → R10134003)

        Returns: lat, lon, full_address, assessed_land_value, assessed_improvement_value,
                 lot_size_acres, lot_size_sqft, zoning_code
        """
        if not self.session:
            self.session = httpx.AsyncClient(timeout=30.0, verify=False)

        gis_account = f"R{parcel_number}"
        params = {
            "where": f"ACCOUNTNO='{gis_account}'",
            "outFields": "LATITUDE,LONGITUDE,SITE_ADDRESS,LANDVALUE,IMPVALUE,PARCEL_SIZE,UNIT_TYPE,USE_CODE",
            "returnGeometry": "false",
            "outSR": "4326",
            "f": "json",
        }
        resp = await self.session.get(self.GIS_URL, params=params, timeout=15)
        data = resp.json()
        features = data.get("features", [])
        if not features:
            return None

        attrs = features[0]["attributes"]

        lat = attrs.get("LATITUDE")
        lon = attrs.get("LONGITUDE")

        # Validate Arizona bounds
        if lat and lon and not (31 <= lat <= 37 and -115 <= lon <= -109):
            lat, lon = None, None

        site_addr = (attrs.get("SITE_ADDRESS") or "").strip() or None

        land_value = attrs.get("LANDVALUE") or None
        imp_value = attrs.get("IMPVALUE") or None

        parcel_size = attrs.get("PARCEL_SIZE")
        unit_type = (attrs.get("UNIT_TYPE") or "").strip().lower()
        lot_acres, lot_sqft = None, None
        if parcel_size:
            if "acre" in unit_type:
                lot_acres = round(parcel_size, 4)
                lot_sqft = int(parcel_size * 43560)
            elif "sq" in unit_type or "feet" in unit_type:
                lot_sqft = int(parcel_size)
                lot_acres = round(parcel_size / 43560, 4)

        use_code = (attrs.get("USE_CODE") or "").strip() or None

        return {
            "latitude": lat,
            "longitude": lon,
            "full_address": site_addr,
            "assessed_land_value": land_value,
            "assessed_improvement_value": imp_value,
            "lot_size_acres": lot_acres,
            "lot_size_sqft": lot_sqft,
            "zoning_code": use_code,
        }

    def _parse_summary(self, html: str) -> dict:
        """Extract owner name, mailing address, situs address, legal description.

        Actual HTML structure (verified against live Mohave EagleWeb):
          <td class='label' valign='top'>Owners</td><td  >HUFFMAN DAVID J</td>
          <td class='label' valign='top'>Address</td><td  >PMB 317 <br>KINGMAN, AZ</td>
          <td class='label' valign='top'>Situs&nbsp;Address</td><td  ></td>
          <td class='label' valign='top'>Legal</td><td  >Section: 29...</td>
        """
        result = {}

        def get_label(label_text: str) -> Optional[str]:
            m = re.search(
                r"<td[^>]*class='label'[^>]*>" + re.escape(label_text) + r"</td><td[^>]*>(.*?)</td>",
                html, re.DOTALL | re.IGNORECASE
            )
            if not m:
                return None
            raw = re.sub(r"<[^>]+>", " ", m.group(1)).strip()
            return re.sub(r"\s+", " ", raw).strip() or None

        # Owner name (label = "Owners")
        name = get_label("Owners")
        if name and len(name) > 2:
            result["owner_name"] = name[:255]

        # Owner mailing address — preserve line breaks before stripping tags
        m = re.search(
            r"<td[^>]*class='label'[^>]*>Address</td><td[^>]*>(.*?)</td>",
            html, re.DOTALL
        )
        if m:
            raw = re.sub(r"<br[^>]*>", " ", m.group(1))
            addr = re.sub(r"<[^>]+>", "", raw).strip()
            addr = re.sub(r"\s+", " ", addr).strip()
            if len(addr) > 5:
                result["owner_mailing_address"] = addr[:500]

        # Situs address (label = "Situs&nbsp;Address" in HTML)
        m = re.search(
            r"<td[^>]*class='label'[^>]*>Situs[^<]*</td><td[^>]*>(.*?)</td>",
            html, re.DOTALL
        )
        if m:
            addr = re.sub(r"<[^>]+>", " ", m.group(1)).strip()
            addr = re.sub(r"\s+", " ", addr).strip()
            if len(addr) > 3:
                result["full_address"] = addr[:500]

        # Legal description (label = "Legal")
        desc = get_label("Legal")
        if desc and len(desc) > 5:
            result["legal_description"] = desc[:1000]

        return result

    def _parse_billing(self, html: str) -> dict:
        """Extract legal class (Property Code) and Full Cash assessed value.

        Actual HTML structure (verified against live Mohave EagleWeb):
          <table class='account stripe'>
            <tr><th>Property Code</th><th>Value Type</th><th>Actual</th><th>Assessed</th></tr>
            <tr><td>AG/VACANT LAND/...</td><td>Full Cash</td><td>$37,137.00</td>...</tr>
            ...
            <tr><td class='total'>Total</td><td class='total'>Full Cash</td>
                <td class='total'>$37,137.00</td><td class='total'>$5,571.00</td></tr>
        """
        result = {}

        # Property Code (legal_class) — first data row in the stripe table
        m = re.search(
            r"<table class='account stripe'>.*?<tr><td(?!\s*class='total')(.*?)>(.*?)</td>",
            html, re.DOTALL
        )
        if m:
            val = re.sub(r"<[^>]+>", "", m.group(2)).strip()
            if val and val.lower() not in ("property code", "total", "value type"):
                result["legal_class"] = val[:255]

        # Full Cash Actual → assessed_total_value (from the Total/Full Cash summary row)
        m = re.search(
            r"<td[^>]*class='total'[^>]*>Total</td>"
            r"<td[^>]*class='total'[^>]*>Full Cash</td>"
            r"<td[^>]*>\$?([\d,]+\.?\d*)</td>",
            html
        )
        if m:
            try:
                result["assessed_total_value"] = float(m.group(1).replace(",", ""))
            except ValueError:
                pass

        return result

    def _parse_tx_history(self, html: str) -> dict:
        """Extract tax payment history metrics (same EagleWeb table structure as Apache)."""
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
            if len(vals) >= 5:
                try:
                    year_data.append({
                        "year": int(year_str),
                        "lien_due": float(vals[4].replace(",", "")) if len(vals) > 4 else 0.0,
                        "total_due": float(vals[-1].replace(",", "")),
                    })
                except (ValueError, IndexError):
                    pass

        if not year_data:
            return result

        prior_liens_count = sum(1 for r in year_data if r["lien_due"] > 0)
        total_outstanding = round(sum(r["total_due"] for r in year_data), 2)
        delinquent_years = [r["year"] for r in year_data if r["total_due"] > 0]
        first_delinquent_year = min(delinquent_years) if delinquent_years else None

        sorted_years = sorted(delinquent_years, reverse=True)
        consecutive = 0
        for i, yr in enumerate(sorted_years):
            if i == 0 or sorted_years[i - 1] - yr == 1:
                consecutive += 1
            else:
                break

        result["years_delinquent"] = consecutive
        result["prior_liens_count"] = prior_liens_count
        result["total_outstanding"] = total_outstanding
        result["first_delinquent_year"] = first_delinquent_year
        return result

    def _build_google_maps_url(self, lat=None, lon=None, address=None, parcel_id=None) -> str:
        import urllib.parse
        if lat and lon:
            return f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
        elif address:
            return f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(address)}"
        elif parcel_id:
            return f"https://www.google.com/maps/search/?api=1&query=Parcel+{parcel_id}+Mohave+County+Arizona"
        return "https://www.google.com/maps/search/?api=1&query=Mohave+County+Arizona"

    def _build_street_view_url(self, lat=None, lon=None, address=None) -> Optional[str]:
        import urllib.parse
        if lat and lon:
            return f"https://www.google.com/maps/@{lat},{lon},3a,75y,0h,90t/data=!3m6!1e1!3m4!1s0!2e0!7i13312!8i6656"
        elif address:
            return f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=&pano={urllib.parse.quote(address)}"
        return None

    def _build_zillow_url(self, address=None, parcel_id=None) -> Optional[str]:
        import urllib.parse
        if address:
            return f"https://www.zillow.com/homes/{urllib.parse.quote(address)}_rb/"
        elif parcel_id:
            return f"https://www.zillow.com/homes/Parcel-{parcel_id}-Mohave-County-AZ_rb/"
        return None

    def _build_realtor_url(self, address=None, parcel_id=None) -> Optional[str]:
        import urllib.parse
        if address:
            return f"https://www.realtor.com/realestateandhomes-search/{urllib.parse.quote(address)}"
        elif parcel_id:
            return f"https://www.realtor.com/realestateandhomes-search/Mohave-County_AZ/parcel-{parcel_id}"
        return None
