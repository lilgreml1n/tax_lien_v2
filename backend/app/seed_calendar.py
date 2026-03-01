"""
Known Arizona (and future) county tax lien auction dates.
Safe to re-run — uses INSERT IGNORE so it never creates duplicates.

Add new counties/dates here as they're discovered.
"""
from sqlalchemy import text
from app.database import engine

KNOWN_EVENTS = [
    # ── Arizona 2026 ──────────────────────────────────────────────────────────
    # Apache: typically 2nd week of February
    {
        "state": "Arizona", "county": "Apache",
        "event_date": "2026-02-10", "event_type": "auction",
        "url": "https://apache.arizonataxsale.com/index.cfm?folder=previewitems",
        "notes": "Apache County annual tax lien sale. ~9,750 parcels."
    },
    # Coconino: typically same window
    {
        "state": "Arizona", "county": "Coconino",
        "event_date": "2026-02-10", "event_type": "auction",
        "url": "https://coconino.arizonataxsale.com/index.cfm?folder=previewitems",
        "notes": "Coconino County annual tax lien sale."
    },
    # Maricopa: Feb 10 2026 confirmed
    {
        "state": "Arizona", "county": "Maricopa",
        "event_date": "2026-02-10", "event_type": "auction",
        "url": "https://maricopa.arizonataxsale.com/index.cfm?folder=previewitems",
        "notes": "Maricopa County annual tax lien sale. Largest county in AZ. Requires registration."
    },
    # Mohave: Feb 2026
    {
        "state": "Arizona", "county": "Mohave",
        "event_date": "2026-02-18", "event_type": "auction",
        "url": "https://mohave.arizonataxsale.com/index.cfm?folder=previewitems",
        "notes": "Mohave County annual tax lien sale. ~8,680 parcels."
    },
    # Gila: Feb 18 2026 confirmed
    {
        "state": "Arizona", "county": "Gila",
        "event_date": "2026-02-18", "event_type": "auction",
        "url": "https://www.gilacountyaz.gov/government/treasurer/tax_lein_sale.php",
        "notes": "Gila County annual tax lien sale. ~400-500 parcels."
    },
    # Yavapai: opens to public 03/02/2026
    {
        "state": "Arizona", "county": "Yavapai",
        "event_date": "2026-03-02", "event_type": "auction",
        "url": "https://yavapai.arizonataxsale.com/index.cfm?folder=previewitems",
        "notes": "Yavapai County auction opens to general public 03/02/2026."
    },
    # Pinal
    {
        "state": "Arizona", "county": "Pinal",
        "event_date": "2026-02-10", "event_type": "auction",
        "url": "https://pinal.arizonataxsale.com/index.cfm?folder=previewitems",
        "notes": "Pinal County annual tax lien sale."
    },

    # ── Nebraska 2026 ─────────────────────────────────────────────────────────
    # Lancaster (Lincoln): first Monday in March
    {
        "state": "Nebraska", "county": "Lancaster",
        "event_date": "2026-03-02", "event_type": "auction",
        "url": "https://www.lancaster.ne.gov/444/Tax-Sale-Information",
        "notes": "Lancaster County NE tax sale. List: lancaster.ne.gov/396/Delinquent-Tax-Listing. Updated weekly until sale date."
    },
    # Sarpy: first Monday in March
    {
        "state": "Nebraska", "county": "Sarpy",
        "event_date": "2026-03-02", "event_type": "auction",
        "url": "https://www.sarpy.gov/981/Tax-Sale-Information",
        "notes": "Sarpy County NE tax sale — first Monday in March."
    },
    # Saline: first Monday in March
    {
        "state": "Nebraska", "county": "Saline",
        "event_date": "2026-03-02", "event_type": "auction",
        "url": "https://salinecountyne.gov/treasurer-office/public-tax-sale-information/",
        "notes": "Saline County NE tax sale — first Monday in March."
    },
    # Douglas (Omaha): internet auction via zeusauction.com, held in November
    {
        "state": "Nebraska", "county": "Douglas",
        "event_date": "2026-11-02", "event_type": "auction",
        "url": "https://www.dctreasurer.org/tax-certificate-sale",
        "notes": "Douglas County NE internet auction via zeusauction.com (SRI). Held on/before 2nd Monday in December. List published in October. Approx date — confirm at dctreasurer.org in Oct."
    },

    # ── Nebraska 2027 (approximate) ───────────────────────────────────────────
    {
        "state": "Nebraska", "county": "Lancaster",
        "event_date": "2027-03-01", "event_type": "auction",
        "url": "https://www.lancaster.ne.gov/444/Tax-Sale-Information",
        "notes": "Lancaster County NE 2027 — first Monday in March (approximate)."
    },
    {
        "state": "Nebraska", "county": "Sarpy",
        "event_date": "2027-03-01", "event_type": "auction",
        "url": "https://www.sarpy.gov/981/Tax-Sale-Information",
        "notes": "Sarpy County NE 2027 — approximate."
    },
    {
        "state": "Nebraska", "county": "Douglas",
        "event_date": "2027-11-01", "event_type": "auction",
        "url": "https://www.dctreasurer.org/tax-certificate-sale",
        "notes": "Douglas County NE 2027 internet auction — approximate November date."
    },

    # ── Arizona 2027 (approximate — update when confirmed) ───────────────────
    {
        "state": "Arizona", "county": "Apache",
        "event_date": "2027-02-09", "event_type": "auction",
        "url": "https://apache.arizonataxsale.com/index.cfm?folder=previewitems",
        "notes": "Apache County 2027 — date approximate (2nd Tuesday Feb)."
    },
    {
        "state": "Arizona", "county": "Coconino",
        "event_date": "2027-02-09", "event_type": "auction",
        "url": "https://coconino.arizonataxsale.com/index.cfm?folder=previewitems",
        "notes": "Coconino County 2027 — date approximate."
    },
    {
        "state": "Arizona", "county": "Yavapai",
        "event_date": "2027-03-01", "event_type": "auction",
        "url": "https://yavapai.arizonataxsale.com/index.cfm?folder=previewitems",
        "notes": "Yavapai County 2027 — date approximate (first Monday March)."
    },
    {
        "state": "Arizona", "county": "Maricopa",
        "event_date": "2027-02-09", "event_type": "auction",
        "url": "https://maricopa.arizonataxsale.com/index.cfm?folder=previewitems",
        "notes": "Maricopa County 2027 — date approximate."
    },
    {
        "state": "Arizona", "county": "Mohave",
        "event_date": "2027-02-17", "event_type": "auction",
        "url": "https://mohave.arizonataxsale.com/index.cfm?folder=previewitems",
        "notes": "Mohave County 2027 — date approximate."
    },
    {
        "state": "Arizona", "county": "Pinal",
        "event_date": "2027-02-09", "event_type": "auction",
        "url": "https://pinal.arizonataxsale.com/index.cfm?folder=previewitems",
        "notes": "Pinal County 2027 — date approximate."
    },
]


def seed_known_events():
    """Insert known events. Safe to call multiple times — skips duplicates."""
    inserted = 0
    with engine.begin() as conn:
        for e in KNOWN_EVENTS:
            result = conn.execute(text("""
                INSERT IGNORE INTO calendar_events
                    (state, county, event_date, event_type, url, notes)
                VALUES
                    (:state, :county, :event_date, :event_type, :url, :notes)
            """), e)
            inserted += result.rowcount
    if inserted:
        print(f"[Calendar] Seeded {inserted} new auction date(s).", flush=True)
