"""
Backfill assessor + GIS + geocoded address data for scraped parcels.

Fetches: owner, assessed value, lot size, legal class, coordinates (ArcGIS),
         street address (SITUS from GIS or ESRI reverse geocode),
         tax payment history (years delinquent, prior liens, total owed).
Assessments are NOT touched.

Run inside Docker:
  docker exec -it tax_lien_v2-backend-1 python /app/app/backfill_bids.py [--bids-only] [--county Arizona/Apache]

───────────────────────────────────────────────────────────────────────────────
ADDING A NEW COUNTY
───────────────────────────────────────────────────────────────────────────────
1. Import the scraper class at the top of this file.
2. Add an entry to COUNTY_REGISTRY below.
3. That's it — all other logic (querying, updating, reverse geocoding) is shared.

Registry fields:
  scraper_class   : The scraper class to instantiate
  login_methods   : List of async method names to call on the scraper before fetching
  fetch_method    : Async method name that returns a dict of parcel fields
  tx_method       : Async method name for tax history, or None if already in fetch_method
  missing_fields  : DB columns to check for NULL — parcel is queued if ANY are NULL
                    (omit "latitude" for counties with no GIS data)
───────────────────────────────────────────────────────────────────────────────
"""
import asyncio
import sys
import os

# Setup paths for local imports
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
os.environ.setdefault('PYTHONPATH', project_root)

import re
import httpx
from sqlalchemy import create_engine, text

from app.scrapers.arizona.apache import ApacheScraper
from app.scrapers.arizona.coconino import CoconinaScraper
from app.scrapers.arizona.yavapai import YavapaiScraper
from app.scrapers.arizona.mohave import MohaveScraper
from app.scrapers.nebraska.douglas import DouglasScraper
from app.scrapers.nebraska.lancaster import LancasterScraper
from app.scrapers.nebraska.sarpy import SarpyScraper
from app.scrapers.nebraska.saline import SalineScraper


def _mohave_parcel_number(row: dict) -> str:
    """Extract parcel number from stored assessor_url for GIS lookup."""
    m = re.search(r'\?parcel=(\d+)', row.get("assessor_url") or "")
    return m.group(1) if m else None

# Support both local iTerm (localhost) and Docker (db)
DEFAULT_DB = "mysql+pymysql://lienuser:lienpass@localhost:3306/lienhunter"
DB_URL = os.getenv("DATABASE_URL", DEFAULT_DB).replace("@db/", "@localhost/") if not os.getenv("IS_DOCKER") else os.getenv("DATABASE_URL", "mysql+pymysql://lienuser:lienpass@db/lienhunter")

engine = create_engine(DB_URL)

ESRI_GEOCODE_URL = "https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/reverseGeocode"

# ─────────────────────────────────────────────────────────────────────────────
# COUNTY REGISTRY — add new counties here
# ─────────────────────────────────────────────────────────────────────────────
COUNTY_REGISTRY = {
    ("Arizona", "Apache"): {
        "scraper_class": ApacheScraper,
        "login_methods": ["_login_treasurer", "_login_assessor"],
        # fetch_fn(scraper, row) → details dict.  row always contains parcel_id + extra_db_fields.
        "fetch_fn": lambda s, row: s._get_parcel_details(row["parcel_id"]),
        "tx_fn":    lambda s, row: s._get_tax_history(row["parcel_id"]),
        "extra_db_fields": [],
        "missing_fields": ["owner_name", "latitude", "assessed_total_value", "years_delinquent"],
    },
    ("Arizona", "Coconino"): {
        "scraper_class": CoconinaScraper,
        "login_methods": ["_login_assessor"],
        "fetch_fn": lambda s, row: s._get_parcel_details(row["parcel_id"]),
        "tx_fn": None,  # no treasurer integration yet
        "extra_db_fields": [],
        "missing_fields": ["owner_name", "assessed_total_value", "lot_size_acres"],
    },
    ("Arizona", "Yavapai"): {
        "scraper_class": YavapaiScraper,
        "login_methods": [],  # no login needed — public auction site
        "fetch_fn": lambda s, row: s._get_parcel_details(row["parcel_id"]),
        "tx_fn": None,  # TODO: wire up after assessor confirmed Monday
        "extra_db_fields": [],
        "missing_fields": ["owner_name", "assessed_total_value", "lot_size_acres"],
    },
    ("Arizona", "Mohave"): {
        "scraper_class": MohaveScraper,
        "login_methods": ["_login_treasurer"],
        # Pass parcel_number (from assessor_url) so GIS lookup runs during backfill
        "fetch_fn": lambda s, row: s._get_eagleweb_details(
            row["parcel_id"],
            parcel_number=_mohave_parcel_number(row),
        ),
        "tx_fn": None,  # already included in _get_eagleweb_details
        "extra_db_fields": ["assessor_url"],  # needed to extract parcel_number
        "missing_fields": ["owner_name", "assessed_total_value", "years_delinquent", "latitude"],
    },
    ("Nebraska", "Douglas"): {
        "scraper_class": DouglasScraper,
        "login_methods": ["_login_assessor", "_login_treasurer"],
        "fetch_fn": lambda s, row: s._get_parcel_details(row["parcel_id"]),
        "tx_fn":    lambda s, row: s._get_tax_history(row["parcel_id"]),
        "extra_db_fields": [],
        "missing_fields": ["owner_name", "assessed_total_value", "legal_description"],
    },
    ("Nebraska", "Lancaster"): {
        "scraper_class": LancasterScraper,
        "login_methods": ["_login_assessor"],
        "fetch_fn": lambda s, row: s._get_parcel_details(row["parcel_id"]),
        "tx_fn":    None,
        "extra_db_fields": [],
        "missing_fields": ["owner_name", "assessed_total_value", "assessed_improvement_value", "legal_description"],
    },
    ("Nebraska", "Sarpy"): {
        "scraper_class": SarpyScraper,
        "login_methods": ["_login_assessor"],
        "fetch_fn": lambda s, row: s._get_parcel_details(row["parcel_id"]),
        "tx_fn":    None,
        "extra_db_fields": [],
        "missing_fields": ["owner_name", "assessed_total_value", "assessed_improvement_value", "legal_description"],
    },
    ("Nebraska", "Saline"): {
        "scraper_class": SalineScraper,
        "login_methods": ["_login_assessor"],
        "fetch_fn": lambda s, row: s._get_parcel_details(row["parcel_id"]),
        "tx_fn":    None,
        "extra_db_fields": [],
        "missing_fields": ["owner_name", "assessed_total_value", "assessed_improvement_value", "legal_description"],
    },
}


async def reverse_geocode(lat: float, lon: float) -> str | None:
    """ESRI World Geocoder reverse geocode — free, no API key, good rural coverage."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(ESRI_GEOCODE_URL, params={
                "location": f"{lon},{lat}",
                "f": "json",
            })
            data = resp.json()
            return data.get("address", {}).get("Match_addr") or None
    except Exception as e:
        print(f"  [Geocode] failed: {e}", flush=True)
        return None


def _build_missing_where(fields: list[str]) -> str:
    """Build SQL OR clause: parcel is queued if ANY of the given fields are NULL."""
    clauses = [f"sp.{f} IS NULL" for f in fields]
    return "(" + " OR ".join(clauses) + ")"


async def backfill_county(state: str, county: str, config: dict, bids_only: bool):
    """Run backfill for a single county using its registry config."""
    missing_where = _build_missing_where(config["missing_fields"])
    extra_fields = config.get("extra_db_fields", [])
    select_fields = ", ".join(["sp.parcel_id"] + [f"sp.{f}" for f in extra_fields])

    with engine.connect() as conn:
        if bids_only:
            rows = conn.execute(text(f"""
                SELECT {select_fields}
                FROM scraped_parcels sp
                JOIN assessments a ON a.parcel_id = sp.id
                WHERE sp.state = :state AND sp.county = :county
                  AND a.decision = 'BID'
                  AND {missing_where}
                ORDER BY a.risk_score DESC
            """), {"state": state, "county": county}).fetchall()
        else:
            rows = conn.execute(text(f"""
                SELECT {select_fields}
                FROM scraped_parcels sp
                LEFT JOIN assessments a ON a.parcel_id = sp.id
                WHERE sp.state = :state AND sp.county = :county
                  AND {missing_where}
                ORDER BY COALESCE(a.risk_score, -1) DESC
            """), {"state": state, "county": county}).fetchall()

    parcel_rows = [dict(r._mapping) for r in rows]
    parcel_ids = [r["parcel_id"] for r in parcel_rows]
    if not parcel_ids:
        print(f"[Backfill] {state}/{county}: all parcels already complete. Nothing to do.", flush=True)
        return

    label = "BID parcels" if bids_only else "parcels"
    print(f"[Backfill] {state}/{county}: {len(parcel_ids)} {label} need backfill.", flush=True)

    scraper = config["scraper_class"](state, county)

    for method_name in config["login_methods"]:
        await getattr(scraper, method_name)()

    fetch_fn = config["fetch_fn"]
    tx_fn    = config.get("tx_fn")

    _notify_counter = 0
    for row in parcel_rows:
        pid = row["parcel_id"]
        try:
            print(f"\n[Backfill] {state}/{county} — fetching {pid}...", flush=True)
            details = await fetch_fn(scraper, row)

            # Don't overwrite existing data with "Unknown" default
            if details.get("legal_class") == "Unknown":
                details["legal_class"] = None

            # Fetch tax history separately if not already included
            if tx_fn:
                await asyncio.sleep(2)
                tx = await tx_fn(scraper, row)
                details.update(tx)

            print(
                f"  [TaxHistory] yrs_delinquent={details.get('years_delinquent')} "
                f"prior_liens={details.get('prior_liens_count')} "
                f"total_owed={details.get('total_outstanding')} "
                f"first_delinquent={details.get('first_delinquent_year')}",
                flush=True,
            )

            # Rebuild map URLs if we got coordinates
            lat = details.get("latitude")
            lon = details.get("longitude")
            if lat and lon:
                details["google_maps_url"] = (
                    f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
                )
                details["street_view_url"] = (
                    f"https://www.google.com/maps/@{lat},{lon},3a,75y,0h,90t"
                    f"/data=!3m6!1e1!3m4!1s0!2e0!7i13312!8i6656"
                )

                # Reverse geocode if no clean situs address
                situs = details.get("full_address") or ""
                # Short values like "39 8105" are lot numbers, not real addresses
                if not situs or len(situs.split()) <= 2:
                    geocoded = await reverse_geocode(lat, lon)
                    if geocoded:
                        details["full_address"] = geocoded
                        print(f"  [Geocode] {pid}: {geocoded}", flush=True)

            with engine.begin() as conn:
                conn.execute(text("""
                    UPDATE scraped_parcels SET
                        full_address               = COALESCE(:full_address, full_address),
                        owner_name                 = COALESCE(:owner_name, owner_name),
                        owner_mailing_address      = COALESCE(:owner_mailing_address, owner_mailing_address),
                        assessed_total_value       = COALESCE(:assessed_total_value, assessed_total_value),
                        assessed_land_value        = COALESCE(:assessed_land_value, assessed_land_value),
                        assessed_improvement_value = COALESCE(:assessed_improvement_value, assessed_improvement_value),
                        legal_description          = COALESCE(:legal_description, legal_description),
                        lot_size_acres             = COALESCE(:lot_size_acres, lot_size_acres),
                        lot_size_sqft              = COALESCE(:lot_size_sqft, lot_size_sqft),
                        legal_class                = COALESCE(:legal_class, legal_class),
                        latitude                   = COALESCE(:latitude, latitude),
                        longitude                  = COALESCE(:longitude, longitude),
                        google_maps_url            = COALESCE(:google_maps_url, google_maps_url),
                        street_view_url            = COALESCE(:street_view_url, street_view_url),
                        years_delinquent           = :years_delinquent,
                        prior_liens_count          = :prior_liens_count,
                        total_outstanding          = :total_outstanding,
                        first_delinquent_year      = :first_delinquent_year
                    WHERE parcel_id = :parcel_id
                """), {
                    "full_address":               details.get("full_address"),
                    "owner_name":                 details.get("owner_name"),
                    "owner_mailing_address":      details.get("owner_mailing_address"),
                    "assessed_total_value":       details.get("assessed_total_value"),
                    "assessed_land_value":        details.get("assessed_land_value"),
                    "assessed_improvement_value": details.get("assessed_improvement_value"),
                    "legal_description":          details.get("legal_description"),
                    "lot_size_acres":             details.get("lot_size_acres"),
                    "lot_size_sqft":              details.get("lot_size_sqft"),
                    "legal_class":                details.get("legal_class"),
                    "latitude":                   details.get("latitude"),
                    "longitude":                  details.get("longitude"),
                    "google_maps_url":            details.get("google_maps_url"),
                    "street_view_url":            details.get("street_view_url"),
                    "years_delinquent":           details.get("years_delinquent"),
                    "prior_liens_count":          details.get("prior_liens_count"),
                    "total_outstanding":          details.get("total_outstanding"),
                    "first_delinquent_year":      details.get("first_delinquent_year"),
                    "parcel_id":                  pid,
                })

            print(
                f"[Backfill] {pid}: owner={details.get('owner_name')} "
                f"value=${details.get('assessed_total_value')} "
                f"acres={details.get('lot_size_acres')} "
                f"lat={details.get('latitude')} "
                f"addr={(details.get('full_address') or '')[:50]}",
                flush=True,
            )

        except Exception as e:
            import traceback
            print(f"[Backfill] {pid}: ERROR - {e}", flush=True)
            traceback.print_exc()

        _notify_counter += 1
        if _notify_counter % 100 == 0:
            from app.discord_notify import post_status
            post_status(state, county)

    await scraper.close()
    from app.discord_notify import post_status
    post_status(state, county, note="✅ Backfill complete!")


async def backfill(bids_only: bool = False, county_key: tuple = None):
    """
    Run backfill for one county (if county_key provided) or all registered counties.

    county_key: tuple of (state, county), e.g. ("Arizona", "Mohave")
    """
    if county_key:
        if county_key not in COUNTY_REGISTRY:
            print(
                f"[Backfill] {county_key} is not in COUNTY_REGISTRY. "
                f"Add it to backfill_bids.py to enable backfill for this county.",
                flush=True,
            )
            return
        counties = [county_key]
    else:
        counties = list(COUNTY_REGISTRY.keys())

    for ck in counties:
        state, county = ck
        config = COUNTY_REGISTRY[ck]
        print(f"\n[Backfill] === {state}/{county} ===", flush=True)
        await backfill_county(state, county, config, bids_only)

    print("\n[Backfill] Done.", flush=True)


if __name__ == "__main__":
    bids_only = "--bids-only" in sys.argv

    county_key = None
    for arg in sys.argv[1:]:
        if arg.startswith("--county="):
            parts = arg.split("=", 1)[1].split("/")
            if len(parts) == 2:
                county_key = (parts[0], parts[1])
        elif arg == "--county" and sys.argv.index(arg) + 1 < len(sys.argv):
            parts = sys.argv[sys.argv.index(arg) + 1].split("/")
            if len(parts) == 2:
                county_key = (parts[0], parts[1])

    asyncio.run(backfill(bids_only=bids_only, county_key=county_key))
