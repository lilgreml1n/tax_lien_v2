import re
import asyncio
import httpx
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional, Callable
from app.scrapers.base import CountyScraper, HumanBehavior, with_retry

class SarpyScraper(CountyScraper):
    """
    Sarpy County, Nebraska (Papillion/Bellevue) Scraper.
    Targets the 'Capture' portal for backfill data:
    - https://apps.sarpy.gov/CaptureCZ/CAPortal/CAMA/CAPortal/CZ_MainPage.aspx
    """

    ASSESSOR_BASE_URL = "https://apps.sarpy.gov/CaptureCZ/CAPortal/CAMA/CAPortal/"

    def __init__(self, state: str = "Nebraska", county: str = "Sarpy"):
        super().__init__(state, county)
        self.assessor_cookies = None

    async def _login_assessor(self):
        """No login required, but initialize session."""
        if not self.session:
            self.session = httpx.AsyncClient(timeout=30.0, verify=False)
        await self.session.get(f"{self.ASSESSOR_BASE_URL}CZ_MainPage.aspx", headers=HumanBehavior.get_headers())

    async def _login_treasurer(self):
        """Treasurer not used for backfill yet."""
        pass

    async def scrape(self, limit: int = 0, start_page: int = 1,
                     on_page_complete: Optional[Callable] = None) -> List[Dict[str, Any]]:
        """
        Sarpy currently uses the PDF ingestor for Phase 1.
        Satisfies the abstract base class requirement.
        """
        return []

    async def _get_parcel_details(self, pid: str) -> dict:
        """
        Fetch details from Sarpy 'Capture' portal.
        Parcel ID format: 9 digits (e.g., 010340459)
        """
        if not self.session:
            self.session = httpx.AsyncClient(timeout=30.0, verify=False)

        details = {
            "owner_name": None,
            "full_address": None,
            "assessed_total_value": None,
            "assessed_land_value": None,
            "assessed_improvement_value": None,
            "legal_description": None,
            "lot_size_acres": None,
            "legal_class": None,
        }

        # Sarpy 'Capture' redirector logic
        url = f"https://maps.sarpy.gov/ering/czredirect.htm?pin={pid}"
        
        try:
            await HumanBehavior.request_delay()
            # Note: For full automation, we'd simulate the POST from czredirect.htm
            # For now, we'll try a direct fetch of the property report
            report_url = f"{self.ASSESSOR_BASE_URL}CZ_PropertyReport.aspx?ParcelID={pid}"
            response = await self.session.get(report_url, headers=HumanBehavior.get_headers(), follow_redirects=True)
            html = response.text
            soup = BeautifulSoup(html, 'html.parser')

            # --- Owner Name ---
            owner_tag = soup.find(id=re.compile(r'tdOIOwnerName|lblOwnerName'))
            if owner_tag:
                details["owner_name"] = owner_tag.get_text(strip=True)

            # --- Property Address ---
            addr_tag = soup.find(id=re.compile(r'tdPropertyAddress|lblAddress'))
            if addr_tag:
                details["full_address"] = addr_tag.get_text(strip=True)

            # --- Values ---
            total_tag = soup.find(id=re.compile(r'tdPropertyValueHeader|lblTotalValue'))
            if total_tag:
                val_text = total_tag.get_text(strip=True).replace("$", "").replace(",", "")
                try:
                    details["assessed_total_value"] = float(val_text)
                except ValueError:
                    pass

        except Exception as e:
            print(f"  [Sarpy] {pid}: Error fetching assessor data: {e}")

        return details

    async def _get_tax_history(self, pid: str) -> dict:
        return {}

    async def close(self):
        if self.session:
            await self.session.aclose()
            self.session = None
