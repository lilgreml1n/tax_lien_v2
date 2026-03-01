import re
import httpx
import openpyxl
import io
import sys
import os
from typing import List, Dict, Any, Callable, Optional
from app.scrapers.base import CountyScraper, HumanBehavior, with_retry

class SalineScraper(CountyScraper):
    """
    Saline County, Nebraska Scraper

    Source: https://www.salinecountyne.gov/treasurer-office/public-tax-sale-information
    Excel Link: https://www.salinecountyne.gov/wp-content/uploads/sites/14/2026/01/2026-ADVERTISING-LIST-FOR-CO-WEBSITE.xlsx
    """

    XLSX_URL = "https://www.salinecountyne.gov/wp-content/uploads/sites/14/2026/01/2026-ADVERTISING-LIST-FOR-CO-WEBSITE.xlsx"
    ASSESSOR_BASE_URL = "https://saline.gworks.com"

    def __init__(self, state: str = "Nebraska", county: str = "Saline"):
        super().__init__(state, county)
        self.total_parcels_available = 0

    async def scrape(self, limit: int = 0, start_page: int = 1,
                     on_page_complete: Optional[Callable] = None) -> List[Dict[str, Any]]:
        """Download Excel, parse it, return parcels."""
        all_parcels: List[Dict[str, Any]] = []

        async with httpx.AsyncClient(timeout=60.0, verify=False) as client:
            print(f"[{self.county}] Downloading Advertising List (XLSX)...", flush=True)
            try:
                await HumanBehavior.request_delay()
                resp = await client.get(self.XLSX_URL, headers=HumanBehavior.get_headers(),
                                      follow_redirects=True)
                resp.raise_for_status()
                
                # Parse Excel from memory
                wb = openpyxl.load_workbook(io.BytesIO(resp.content), data_only=True)
                sheet = wb.active
                
                # Columns: ITEM # | PARCEL | NAME | PROPERTY ADDRESS | LEGAL | UNPAID PRINCIPLE
                # Data starts at row 3 (Row 1: Header, Row 2: Empty)
                for row in sheet.iter_rows(min_row=3, values_only=True):
                    if not row[1]: # Skip empty rows (Parcel ID missing)
                        continue
                        
                    parcel_id = str(row[1]).strip()
                    owner = str(row[2]).strip() if row[2] else None
                    address = str(row[3]).strip() if row[3] else None
                    legal = str(row[4]).strip() if row[4] else ""
                    billed = float(row[5]) if row[5] is not None else 0.0
                    
                    # Extract acreage from legal if present (e.g., "196.39 ACRES")
                    acres = None
                    acre_match = re.search(r'([\d,.]+)\s*ACRE', legal, re.IGNORECASE)
                    if acre_match:
                        try:
                            acres = float(acre_match.group(1).replace(',', ''))
                        except ValueError:
                            pass

                    all_parcels.append({
                        "state": self.state,
                        "county": self.county,
                        "parcel_id": parcel_id,
                        "billed_amount": billed,
                        "full_address": address if address and "PRCT" not in address else None,
                        "owner_name": owner,
                        "legal_description": legal,
                        "lot_size_acres": acres,
                        "source_url": self.XLSX_URL,
                        "assessor_url": f"{self.ASSESSOR_BASE_URL}/?parcel={parcel_id}",
                        # Initialized for backfill
                        "latitude": None,
                        "longitude": None,
                        "lot_size_sqft": None,
                        "assessed_land_value": None,
                        "assessed_improvement_value": None,
                        "assessed_total_value": None,
                        "legal_class": None,
                        "owner_mailing_address": None,
                        "zoning_code": None,
                        "zoning_description": None,
                        "google_maps_url": None,
                        "street_view_url": None,
                        "zillow_url": None,
                        "realtor_url": None,
                        "treasurer_url": None,
                    })
                    
                print(f"[{self.county}] Parsed {len(all_parcels)} parcels from Excel", flush=True)
                
            except Exception as e:
                print(f"[{self.county}] Error: {e}", flush=True)

        # MANDATORY: Set total BEFORE limit
        self.total_parcels_available = len(all_parcels)

        if limit > 0:
            all_parcels = all_parcels[:limit]

        # MANDATORY: Fire callback
        if on_page_complete and all_parcels:
            on_page_complete(all_parcels, 1)

        return all_parcels

    # ── Assessor Backfill ──────────────────────────────────────────

    async def _login_assessor(self):
        """No login needed for gWorks public access."""
        if not self.session:
            self.session = httpx.AsyncClient(timeout=30.0, verify=False)
        await self.session.get(self.ASSESSOR_BASE_URL, headers=HumanBehavior.get_headers())

    async def _login_treasurer(self):
        pass

    async def _get_parcel_details(self, pid: str) -> dict:
        """
        Fetch property details from gWorks.
        Note: gWorks often requires Playwright for deep scraping,
        but simple fields can sometimes be grabbed via JSON endpoints.
        For now, returns empty dict to be filled by backfill process.
        """
        return {}

    async def close(self):
        if self.session:
            await self.session.aclose()
            self.session = None
