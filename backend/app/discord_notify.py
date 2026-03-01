"""
Discord webhook notifications for LienHunter progress updates.

Sends a combined status message showing scrape / backfill / assessment progress
for a given state/county. Call post_status() from any background thread.
"""
import os
import httpx
from sqlalchemy import text
from app.database import engine

WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")


def _get_counts(state: str, county: str) -> dict:
    """Query DB for current scrape / backfill / assessment counts."""
    try:
        with engine.connect() as conn:
            # Scraping: parcels saved
            cp = conn.execute(text("""
                SELECT total_parcels_scraped
                FROM scraper_checkpoints
                WHERE state = :s AND county = :c
            """), {"s": state, "c": county}).fetchone()
            total_scraped = cp[0] if cp else 0

            # Backfill proxy: parcels with GIS data (latitude populated)
            bf = conn.execute(text("""
                SELECT COUNT(*) FROM scraped_parcels
                WHERE state = :s AND county = :c AND latitude IS NOT NULL
            """), {"s": state, "c": county}).fetchone()
            total_backfilled = bf[0] if bf else 0

            # Assessments
            agg = conn.execute(text("""
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN a.decision = 'BID'        THEN 1 ELSE 0 END) AS bids,
                    SUM(CASE WHEN a.decision = 'DO_NOT_BID' THEN 1 ELSE 0 END) AS no_bids
                FROM assessments a
                JOIN scraped_parcels sp ON sp.id = a.parcel_id
                WHERE sp.state = :s AND sp.county = :c
                  AND a.assessment_status = 'assessed'
            """), {"s": state, "c": county}).fetchone()
            total_assessed = agg[0] or 0
            total_bid      = agg[1] or 0
            total_no_bid   = agg[2] or 0

        return {
            "scraped":    total_scraped,
            "backfilled": total_backfilled,
            "assessed":   total_assessed,
            "bid":        total_bid,
            "no_bid":     total_no_bid,
        }
    except Exception:
        return {"scraped": 0, "backfilled": 0, "assessed": 0, "bid": 0, "no_bid": 0}


def post_status(state: str, county: str, note: str = ""):
    """
    Send a combined status message to Discord.
    Safe to call from any thread — uses synchronous httpx.
    Silently does nothing if DISCORD_WEBHOOK_URL is not set.
    """
    if not WEBHOOK_URL:
        return

    try:
        c = _get_counts(state, county)
        lines = [
            f"**LienHunter — {county} County, {state}**",
            f"🔍  Scraping:    {c['scraped']:,} parcels saved",
            f"🔄  Backfill:    {c['backfilled']:,} parcels with GIS data",
            f"🤖  Assessment:  {c['assessed']:,} assessed  •  {c['bid']:,} BID  •  {c['no_bid']:,} DO_NOT_BID",
        ]
        if note:
            lines.append(f"ℹ️   {note}")

        with httpx.Client(timeout=10) as client:
            client.post(WEBHOOK_URL, json={"content": "\n".join(lines)})

    except Exception as e:
        print(f"[Discord] Notify failed: {e}", flush=True)
