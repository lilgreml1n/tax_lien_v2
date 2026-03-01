"""
Lancaster County, Nebraska Scraper

Sources:
- Main delinquent tax list (PDF):
    https://app.lincoln.ne.gov/cnty/treasurer/adlist/adlist.pdf
- Special assessments (PDF):
    https://www.lancaster.ne.gov/DocumentCenter/View/3940/Advertised-Delinquent-Special-Assessments-PDF
- Assessor (backfill):
    https://orion.lancaster.ne.gov/Property-Detail/PropertyNumber/{parcel_no_no_dashes}

Parcel ID format: 16-16-320-001-000  (2-2-3-3-3 groups)
PDF is updated weekly until the March sale date.

PDF line format (pdftotext -layout style):
  SUBD_CODE  DESCRIPTION  B000 L001  16-16-320-001-000  TAX_DUE  TAXABLE  INTEREST  ADDRESS  CLASS
  (next line) OWNER_NAME  MAILING_ADDRESS  CITY  ST  ZIP  Total Millage: X%
"""
import io
import re
import httpx
import pdfplumber
from typing import List, Dict, Any, Callable, Optional

from app.scrapers.base import CountyScraper, HumanBehavior

MAIN_PDF_URL        = "https://app.lincoln.ne.gov/cnty/treasurer/adlist/adlist.pdf"
SPECIAL_PDF_URL     = "https://www.lancaster.ne.gov/DocumentCenter/View/3940/Advertised-Delinquent-Special-Assessments-PDF"
ASSESSOR_BASE_URL   = "https://orion.lancaster.ne.gov/Property-Detail/PropertyNumber"

# Parcel line: SubdCode  Description  Block  Lot  ParcelID  TaxDue  Taxable  Interest  Address  Class
PARCEL_RE = re.compile(
    r'^\S+\s+.{1,50}\s+(B[\w]{3,6})\s+(L\d{1,4}(?:\s+[A-Z])?)\s+(\d{2}-\d{2}-\d{3}-\d{3}-\d{3})\s+'
    r'([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+(.{1,65}?)\s*([A-Z][A-Z0-9]{0,3})\s*$',
    re.MULTILINE
)


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract layout-preserved text from PDF bytes using pdfplumber."""
    text_parts = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text(layout=True)
            if text:
                text_parts.append(text)
    return "\n".join(text_parts)


def _parse_pdf_text(text: str, source_url: str) -> List[Dict[str, Any]]:
    """
    Parse pdftotext-style layout text into parcel dicts.
    Owner name is on the line immediately following the parcel line.
    """
    parcels = []
    lines = text.split("\n")

    for i, line in enumerate(lines):
        m = PARCEL_RE.match(line.strip())
        if not m:
            continue

        parcel_id   = m.group(3)
        billed      = float(m.group(4).replace(",", ""))
        taxable_val = float(m.group(5).replace(",", ""))
        address     = m.group(7).strip()
        legal_class = m.group(8).strip()

        # Owner name is on the next non-empty line
        owner_name = None
        if i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            if next_line and not PARCEL_RE.match(next_line):
                # Owner name is the first ~30 chars before the mailing address begins
                owner_match = re.match(r'^(.{3,40?})\s{3,}', next_line)
                owner_name = owner_match.group(1).strip() if owner_match else next_line[:40].strip()

        parcels.append({
            "state":                "Nebraska",
            "county":               "Lancaster",
            "parcel_id":            parcel_id,
            "billed_amount":        billed,
            "assessed_total_value": taxable_val,
            "full_address":         address if address and "NO SITUS" not in address else None,
            "owner_name":           owner_name,
            "legal_class":          legal_class,
            "source_url":           source_url,
            "assessor_url":         f"{ASSESSOR_BASE_URL}/{parcel_id.replace('-', '')}",
            # These come from assessor backfill
            "latitude":             None,
            "longitude":            None,
            "lot_size_acres":       None,
            "lot_size_sqft":        None,
            "assessed_land_value":  None,
            "assessed_improvement_value": None,
            "legal_description":    None,
            "owner_mailing_address": None,
            "zoning_code":          None,
            "zoning_description":   None,
            "google_maps_url":      None,
            "street_view_url":      None,
            "zillow_url":           None,
            "realtor_url":          None,
            "treasurer_url":        None,
        })

    return parcels


class LancasterScraper(CountyScraper):

    def __init__(self, state: str = "Nebraska", county: str = "Lancaster"):
        super().__init__(state, county)
        self.assessor_cookies = None

    async def scrape(self, limit: int = 0, start_page: int = 1,
                     on_page_complete: Optional[Callable] = None) -> List[Dict[str, Any]]:
        """
        Download both Lancaster delinquent PDFs, parse them, return parcel list.
        'start_page' and pagination don't apply here — PDFs are full-list snapshots.
        """
        all_parcels: List[Dict[str, Any]] = []

        async with httpx.AsyncClient(timeout=60.0, verify=False) as client:
            for url, label in [
                (MAIN_PDF_URL,    "Main delinquent list"),
                (SPECIAL_PDF_URL, "Special assessments"),
            ]:
                print(f"[Lancaster] Downloading {label}...", flush=True)
                try:
                    await HumanBehavior.request_delay()
                    resp = await client.get(url, headers=HumanBehavior.get_headers(),
                                            follow_redirects=True)
                    resp.raise_for_status()
                    text = _extract_pdf_text(resp.content)
                    parcels = _parse_pdf_text(text, source_url=url)
                    print(f"[Lancaster] Parsed {len(parcels)} parcels from {label}", flush=True)
                    all_parcels.extend(parcels)
                except Exception as e:
                    print(f"[Lancaster] Failed to fetch/parse {label}: {e}", flush=True)

        # Deduplicate by parcel_id (main list takes priority over special assessments)
        seen: set = set()
        unique: List[Dict[str, Any]] = []
        for p in all_parcels:
            if p["parcel_id"] not in seen:
                unique.append(p)
                seen.add(p["parcel_id"])

        self.total_parcels_available = len(unique)  # Known upfront from PDF

        if limit > 0:
            unique = unique[:limit]

        print(f"[Lancaster] Total unique parcels: {len(unique)} (available: {self.total_parcels_available})", flush=True)

        # Fire callback so the API saves them in batches (same pattern as Apache)
        if on_page_complete and unique:
            on_page_complete(unique, 1)

        return unique

    # ── Assessor backfill ─────────────────────────────────────────────────────

    async def _login_assessor(self):
        """Public access — no login needed."""
        if not self.session:
            self.session = httpx.AsyncClient(timeout=30.0, verify=False)
        await self.session.get(ASSESSOR_BASE_URL, headers=HumanBehavior.get_headers())

    async def _login_treasurer(self):
        """Not used."""
        pass

    async def _get_parcel_details(self, pid: str) -> dict:
        """
        Fetch property details from Orion (Lancaster assessor).
        Parcel ID: 16-16-320-001-000 → strip dashes → 1616320001000
        """
        if not self.session:
            self.session = httpx.AsyncClient(timeout=30.0, verify=False)

        details = {
            "owner_name":                 None,
            "owner_mailing_address":      None,
            "full_address":               None,
            "assessed_total_value":       None,
            "assessed_land_value":        None,
            "assessed_improvement_value": None,
            "legal_description":          None,
            "lot_size_acres":             None,
            "legal_class":                None,
        }

        clean_pid = pid.replace("-", "")
        url = f"{ASSESSOR_BASE_URL}/{clean_pid}"

        try:
            await HumanBehavior.request_delay()
            resp = await self.session.get(url, headers=HumanBehavior.get_headers(),
                                          follow_redirects=True)
            html = resp.text
        except Exception as e:
            print(f"[Lancaster] {pid}: assessor fetch failed - {e}", flush=True)
            return details

        # Owner name
        m = re.search(r'Owner\s*Name[^:]*:\s*<[^>]+>\s*([^<]+)', html, re.IGNORECASE)
        if not m:
            m = re.search(r'"ownerName"\s*:\s*"([^"]+)"', html)
        if m:
            details["owner_name"] = m.group(1).strip()[:255]

        # Mailing address
        m = re.search(r'Mailing\s*Address[^:]*:\s*<[^>]+>\s*([^<]+)', html, re.IGNORECASE)
        if m:
            details["owner_mailing_address"] = m.group(1).strip()[:500]

        # Situs / property address
        m = re.search(r'Situs\s*Address[^:]*:\s*<[^>]+>\s*([^<]+)', html, re.IGNORECASE)
        if m:
            addr = m.group(1).strip()
            if len(addr) > 3:
                details["full_address"] = addr

        # Assessed values
        for pattern, field in [
            (r'Land\s*Value[^:]*:\s*\$?([\d,]+)', "assessed_land_value"),
            (r'Improvement\s*Value[^:]*:\s*\$?([\d,]+)', "assessed_improvement_value"),
            (r'Total\s*(?:Assessed\s*)?Value[^:]*:\s*\$?([\d,]+)', "assessed_total_value"),
        ]:
            m = re.search(pattern, html, re.IGNORECASE)
            if m:
                try:
                    details[field] = float(m.group(1).replace(",", ""))
                except ValueError:
                    pass

        # Legal description
        m = re.search(r'Legal\s*Description[^:]*:\s*<[^>]+>\s*([^<]{10,500})', html, re.IGNORECASE)
        if m:
            details["legal_description"] = m.group(1).strip()[:1000]

        # Lot size
        m = re.search(r'Lot\s*Size[^:]*:\s*([\d.]+)\s*(acres?|sq\s*ft)', html, re.IGNORECASE)
        if m:
            try:
                val = float(m.group(1))
                unit = m.group(2).lower()
                if "acre" in unit:
                    details["lot_size_acres"] = val
                else:
                    details["lot_size_acres"] = round(val / 43560, 4)
            except ValueError:
                pass

        return details
