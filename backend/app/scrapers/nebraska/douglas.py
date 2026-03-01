import asyncio
import re
import httpx
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional, Callable
from app.scrapers.base import CountyScraper, HumanBehavior, with_retry

class DouglasScraper(CountyScraper):
    """
    Douglas County, Nebraska (Omaha) Scraper.
    Uses:
      - Realauction (Auction items): https://douglas.ne.realtaxlien.com/
      - Assessor (Beacon/SchneiderCorp): https://beacon.schneidercorp.com/Application.aspx?App=DouglasCountyNE&PageType=Search
      - Treasurer: https://payments.dctreasurer.org/search.xhtml
    """

    def __init__(self, state="Nebraska", county="Douglas"):
        super().__init__(state, county)
        self.base_url_assessor = "https://beacon.schneidercorp.com/Application.aspx?App=DouglasCountyNE"
        self.auction_url = "https://douglas.ne.realtaxlien.com/index.cfm?folder=previewitems"

    async def _login_assessor(self):
        """No login required for guest access."""
        if not self.session:
            self.session = httpx.AsyncClient(timeout=30.0, verify=False)
        await self.session.get(self.base_url_assessor, headers=HumanBehavior.get_headers())

    async def _login_treasurer(self):
        """Placeholder for treasurer login if needed."""
        pass

    async def scrape(self, limit: int = 0, start_page: int = 1, 
                     on_page_complete: Optional[Callable] = None) -> List[Dict[str, Any]]:
        """
        Phase 1: Scrape auction listings from Realauction.
        Realauction sites often require Playwright for full interaction,
        but we can try a direct fetch of the preview items first.
        """
        if not self.session:
            self.session = httpx.AsyncClient(timeout=30.0, verify=False)
            
        all_liens = []
        # Realauction pagination is usually via 'start_row' or similar.
        # We'll implement a basic structure here.
        print(f"  [Douglas] Scraping auction preview items...")
        
        try:
            # Note: Realauction might block simple httpx, 
            # if so, this should be moved to a Playwright implementation.
            await HumanBehavior.request_delay()
            resp = await self.session.get(self.auction_url, headers=HumanBehavior.get_headers())
            
            if resp.status_code != 200:
                print(f"  [Douglas] Failed to fetch auction items: {resp.status_code}")
                return all_liens

            # Parse auction items (this is a placeholder until we confirm selectors)
            # soup = BeautifulSoup(resp.text, 'html.parser')
            # items = soup.find_all(...)
            
            # For now, we rely on the PDF ingestor for immediate data,
            # and this scraper for the "Next Year" plumbing.
            
        except Exception as e:
            print(f"  [Douglas] Scrape error: {e}")

        return all_liens

    async def _get_parcel_details(self, parcel_id: str) -> dict:
        """
        Fetch basic property info from the Assessor (Beacon) site.
        Parcel ID format: 10 digits (e.g., 0708610000)
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

        # Douglas Beacon direct PIN access
        url = f"{self.base_url_assessor}&PageType=Property&KeyValue={parcel_id}"
        
        try:
            await HumanBehavior.request_delay()
            resp = await self.session.get(url, headers=HumanBehavior.get_headers())
            if resp.status_code != 200:
                print(f"  [Douglas] Assessor request failed: {resp.status_code}")
                return details

            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Robust Beacon Selectors
            owner_tag = soup.find(id=re.compile(r'lblOwnerName|OwnerName'))
            if owner_tag:
                details["owner_name"] = owner_tag.get_text(strip=True)

            addr_tag = soup.find(id=re.compile(r'lblPropertyAddress|PropertyAddress'))
            if addr_tag:
                details["full_address"] = addr_tag.get_text(strip=True)

            # Valuation History Table (for improvement value)
            hist_table = soup.find(id=re.compile(r'dgValuationHistory'))
            if hist_table:
                # Usually: Year | Land | Improvement | Total
                rows = hist_table.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 4:
                        try:
                            details["assessed_land_value"] = float(cells[1].get_text(strip=True).replace("$", "").replace(",", ""))
                            details["assessed_improvement_value"] = float(cells[2].get_text(strip=True).replace("$", "").replace(",", ""))
                            details["assessed_total_value"] = float(cells[3].get_text(strip=True).replace("$", "").replace(",", ""))
                            break # Get most recent
                        except ValueError:
                            continue

            legal_tag = soup.find(id=re.compile(r'lblLegalDescription|LegalDescription'))
            if legal_tag:
                details["legal_description"] = legal_tag.get_text(strip=True)

        except Exception as e:
            print(f"  [Douglas] {parcel_id}: Error fetching assessor data: {e}")

        return details

    async def _get_tax_history(self, parcel_id: str) -> dict:
        """Fetch tax history (placeholder)."""
        return {}

    async def close(self):
        if self.session:
            await self.session.aclose()
            self.session = None
