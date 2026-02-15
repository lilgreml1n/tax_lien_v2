import os
import re
import threading
import random
import time
import traceback
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from app.database import engine

router = APIRouter(prefix="/scrapers", tags=["Scrapers"])

# ==================== Models ====================

class ScraperConfigIn(BaseModel):
    state: str
    county: str
    scraper_name: str
    scraper_version: str = "1.0"

class JobOut(BaseModel):
    job_id: str
    status: str
    started_at: str

# ==================== Scraper Config ====================

@router.post("/config", tags=["Scrapers", "Config"])
def upsert_scraper_config(item: ScraperConfigIn):
    """Register or update a scraper for a state/county."""
    with engine.begin() as conn:
        existing = conn.execute(
            text("SELECT id FROM scraper_configs WHERE state = :state AND county = :county"),
            {"state": item.state, "county": item.county}
        ).scalar()
        if existing:
            conn.execute(
                text("UPDATE scraper_configs SET scraper_name = :scraper_name, scraper_version = :scraper_version WHERE id = :id"),
                {"scraper_name": item.scraper_name, "scraper_version": item.scraper_version, "id": existing}
            )
            return {"id": existing, "status": "updated"}
        else:
            conn.execute(
                text("INSERT INTO scraper_configs (state, county, scraper_name, scraper_version) VALUES (:state, :county, :scraper_name, :scraper_version)"),
                item.model_dump()
            )
            new_id = conn.execute(text("SELECT LAST_INSERT_ID()")).scalar()
            return {"id": new_id, "status": "created"}

@router.get("/config", tags=["Scrapers", "Config"])
def list_scraper_configs():
    """List all registered scrapers."""
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT * FROM scraper_configs ORDER BY state, county")).mappings().all()
    return rows

# ==================== Phase 1: Scrape ====================

@router.post("/scrape/{state}/{county}", response_model=JobOut, tags=["Scrapers", "Scrape"])
def scrape(state: str, county: str, limit: int = 10):
    """Phase 1: Scrape parcels from county website. Saves raw data to DB. No AI."""
    with engine.connect() as conn:
        cfg = conn.execute(
            text("SELECT * FROM scraper_configs WHERE state = :state AND county = :county"),
            {"state": state, "county": county}
        ).mappings().first()
    if not cfg:
        raise HTTPException(status_code=404, detail=f"No scraper configured for {state}/{county}")

    cfg_dict = dict(cfg)
    job_id = f"scrape_{state}_{county}_{int(datetime.now().timestamp())}"

    t = threading.Thread(target=_scrape_thread, args=(job_id, state, county, cfg_dict, limit), daemon=True)
    t.start()

    return JobOut(job_id=job_id, status="scraping", started_at=datetime.now().isoformat())

# ==================== Phase 2: Assess ====================

@router.post("/assess/{state}/{county}", response_model=JobOut, tags=["Scrapers", "Assess"])
def assess(state: str, county: str, batch_size: int = 10, max_cost: float = None):
    """Phase 2: Run Capital Guardian AI on unassessed parcels via DGX Ollama.

    Args:
        state: State name
        county: County name
        batch_size: Number of parcels per batch
        max_cost: Optional max billed amount to assess. Skip more expensive parcels.
                 Example: max_cost=5000 only assesses parcels with billed_amount <= $5,000
    """
    with engine.connect() as conn:
        # Build query with optional cost filter
        if max_cost:
            query = """SELECT COUNT(*) FROM scraped_parcels sp
                    LEFT JOIN assessments a ON a.parcel_id = sp.id
                    WHERE sp.state = :state AND sp.county = :county AND a.id IS NULL
                    AND (sp.billed_amount IS NULL OR sp.billed_amount <= :max_cost)"""
            params = {"state": state, "county": county, "max_cost": max_cost}
        else:
            query = """SELECT COUNT(*) FROM scraped_parcels sp
                    LEFT JOIN assessments a ON a.parcel_id = sp.id
                    WHERE sp.state = :state AND sp.county = :county AND a.id IS NULL"""
            params = {"state": state, "county": county}

        count = conn.execute(text(query), params).scalar()

    if count == 0:
        detail = f"No unassessed parcels for {state}/{county}"
        if max_cost:
            detail += f" with cost <= ${max_cost:,.2f}"
        raise HTTPException(status_code=404, detail=detail)

    job_id = f"assess_{state}_{county}_{int(datetime.now().timestamp())}"

    t = threading.Thread(target=_assess_thread, args=(job_id, state, county, batch_size, max_cost), daemon=True)
    t.start()

    status_msg = f"assessing ({count} pending)"
    if max_cost:
        status_msg += f" [budget filter: max ${max_cost:,.2f}]"

    return JobOut(job_id=job_id, status=status_msg, started_at=datetime.now().isoformat())

# ==================== Query Results ====================

@router.get("/parcels/{state}/{county}", tags=["Scrapers", "Results"])
def get_parcels(state: str, county: str, limit: int = 100):
    """Get all scraped parcels for a county with their assessment status and mapping URLs."""
    with engine.connect() as conn:
        rows = conn.execute(
            text("""SELECT sp.id, sp.state, sp.county, sp.parcel_id, sp.address,
                           sp.latitude, sp.longitude, sp.full_address, sp.google_maps_url,
                           sp.assessor_url, sp.treasurer_url, sp.billed_amount, sp.legal_class,
                           sp.scraped_at, sp.scrape_batch_id,
                           a.decision, a.risk_score, a.kill_switch, a.max_bid,
                           a.property_type, a.ownership_type, a.critical_warning,
                           a.assessment_status, a.review_status
                    FROM scraped_parcels sp
                    LEFT JOIN assessments a ON a.parcel_id = sp.id
                    WHERE sp.state = :state AND sp.county = :county
                    ORDER BY a.risk_score DESC, sp.scraped_at DESC
                    LIMIT :limit"""),
            {"state": state, "county": county, "limit": limit}
        ).mappings().all()
    return rows

@router.get("/unassessed/{state}/{county}", tags=["Scrapers", "Results"])
def get_unassessed(state: str, county: str):
    """How many parcels still need Capital Guardian assessment?"""
    with engine.connect() as conn:
        count = conn.execute(
            text("""SELECT COUNT(*) FROM scraped_parcels sp
                    LEFT JOIN assessments a ON a.parcel_id = sp.id
                    WHERE sp.state = :state AND sp.county = :county AND a.id IS NULL"""),
            {"state": state, "county": county}
        ).scalar()
        sample = conn.execute(
            text("""SELECT sp.id, sp.parcel_id, sp.billed_amount, sp.legal_class
                    FROM scraped_parcels sp
                    LEFT JOIN assessments a ON a.parcel_id = sp.id
                    WHERE sp.state = :state AND sp.county = :county AND a.id IS NULL
                    LIMIT 10"""),
            {"state": state, "county": county}
        ).mappings().all()
    return {"unassessed_count": count, "sample": sample}

@router.get("/bids", tags=["Scrapers", "Results"])
def get_bids(state: Optional[str] = None, limit: int = 100):
    """Get all parcels Capital Guardian said BID on."""
    query = """SELECT sp.*, a.decision, a.risk_score, a.max_bid, a.property_type,
                      a.ownership_type, a.critical_warning, a.review_status
               FROM assessments a
               JOIN scraped_parcels sp ON sp.id = a.parcel_id
               WHERE a.decision = 'BID'"""
    params = {}
    if state:
        query += " AND sp.state = :state"
        params["state"] = state
    query += " ORDER BY a.risk_score DESC LIMIT :limit"
    params["limit"] = limit
    with engine.connect() as conn:
        rows = conn.execute(text(query), params).mappings().all()
    return rows

@router.get("/rejects", tags=["Scrapers", "Results"])
def get_rejects(state: Optional[str] = None, limit: int = 100):
    """Get all parcels Capital Guardian rejected, with reasons."""
    query = """SELECT sp.parcel_id, sp.state, sp.county, sp.billed_amount,
                      a.risk_score, a.kill_switch, a.critical_warning
               FROM assessments a
               JOIN scraped_parcels sp ON sp.id = a.parcel_id
               WHERE a.decision = 'DO_NOT_BID'"""
    params = {}
    if state:
        query += " AND sp.state = :state"
        params["state"] = state
    query += " ORDER BY sp.scraped_at DESC LIMIT :limit"
    params["limit"] = limit
    with engine.connect() as conn:
        rows = conn.execute(text(query), params).mappings().all()
    return rows

@router.get("/pipeline-status/{state}/{county}", tags=["Scrapers", "Results"])
def pipeline_status(state: str, county: str):
    """Overview of the full pipeline for a county."""
    with engine.connect() as conn:
        scraped = conn.execute(
            text("SELECT COUNT(*) FROM scraped_parcels WHERE state = :state AND county = :county"),
            {"state": state, "county": county}
        ).scalar()
        assessed = conn.execute(
            text("""SELECT COUNT(*) FROM assessments a
                    JOIN scraped_parcels sp ON sp.id = a.parcel_id
                    WHERE sp.state = :state AND sp.county = :county AND a.assessment_status = 'assessed'"""),
            {"state": state, "county": county}
        ).scalar()
        bids = conn.execute(
            text("""SELECT COUNT(*) FROM assessments a
                    JOIN scraped_parcels sp ON sp.id = a.parcel_id
                    WHERE sp.state = :state AND sp.county = :county AND a.decision = 'BID'"""),
            {"state": state, "county": county}
        ).scalar()
        reviewed = conn.execute(
            text("""SELECT COUNT(*) FROM assessments a
                    JOIN scraped_parcels sp ON sp.id = a.parcel_id
                    WHERE sp.state = :state AND sp.county = :county AND a.review_status = 'approved'"""),
            {"state": state, "county": county}
        ).scalar()
    return {
        "state": state,
        "county": county,
        "scraped": scraped,
        "assessed": assessed,
        "unassessed": scraped - assessed,
        "bids": bids,
        "do_not_bids": assessed - bids,
        "human_approved": reviewed,
    }

# ==================== Background: Scrape Thread ====================

SCRAPER_REGISTRY = {
    "app.scrapers.arizona.apache.ApacheScraper": None,
    "app.scrapers.arizona.coconino.CoconinoCraper": None,
}

def _get_scraper_class(name: str):
    """Dynamically load a scraper class."""
    parts = name.rsplit(".", 1)
    if len(parts) != 2:
        return None
    module_path, class_name = parts
    try:
        module = __import__(module_path, fromlist=[class_name])
        return getattr(module, class_name, None)
    except (ImportError, AttributeError) as e:
        print(f"Failed to load scraper {name}: {e}", flush=True)
        return None

def _scrape_thread(job_id: str, state: str, county: str, cfg: dict, limit: int):
    import asyncio
    print(f"[{job_id}] Starting scrape (limit={limit})...", flush=True)

    try:
        scraper_class = _get_scraper_class(cfg["scraper_name"])
        if not scraper_class:
            print(f"[{job_id}] Scraper class not found: {cfg['scraper_name']}", flush=True)
            return

        loop = asyncio.new_event_loop()
        scraper = scraper_class(state, county)
        liens = loop.run_until_complete(scraper.scrape(limit=limit))
        loop.close()

        if not liens:
            print(f"[{job_id}] No parcels scraped", flush=True)
            return

        total_parcels = len(liens)
        print(f"[{job_id}] Saving {total_parcels} parcels (batch size: 10)...", flush=True)

        BATCH_SIZE = 10
        total_saved = 0

        # Save in batches of 10 for crash resilience
        for i in range(0, total_parcels, BATCH_SIZE):
            batch = liens[i:i + BATCH_SIZE]
            with engine.begin() as conn:
                for lien in batch:
                    conn.execute(
                        text("""INSERT IGNORE INTO scraped_parcels
                                (state, county, parcel_id, address, latitude, longitude, full_address,
                                 google_maps_url, street_view_url, assessor_url, treasurer_url,
                                 source_url, auction_url, scrape_batch_id,
                                 lot_size_acres, lot_size_sqft, zoning_code, zoning_description,
                                 assessed_land_value, assessed_improvement_value, assessed_total_value,
                                 legal_description, zillow_url, realtor_url,
                                 billed_amount, legal_class, owner_name, owner_mailing_address, scraper_config_id)
                                VALUES (:state, :county, :parcel_id, :address, :latitude, :longitude, :full_address,
                                        :google_maps_url, :street_view_url, :assessor_url, :treasurer_url,
                                        :source_url, :auction_url, :scrape_batch_id,
                                        :lot_size_acres, :lot_size_sqft, :zoning_code, :zoning_description,
                                        :assessed_land_value, :assessed_improvement_value, :assessed_total_value,
                                        :legal_description, :zillow_url, :realtor_url,
                                        :billed_amount, :legal_class, :owner_name, :owner_mailing_address, :cfg_id)"""),
                        {
                            "state": lien["state"],
                            "county": lien["county"],
                            "parcel_id": lien["parcel_id"],
                            "address": lien.get("address", ""),
                            "latitude": lien.get("latitude"),
                            "longitude": lien.get("longitude"),
                            "full_address": lien.get("full_address"),
                            "google_maps_url": lien.get("google_maps_url"),
                            "street_view_url": lien.get("street_view_url"),
                            "assessor_url": lien.get("assessor_url"),
                            "treasurer_url": lien.get("treasurer_url"),
                            "source_url": lien.get("source_url"),
                            "auction_url": lien.get("auction_url"),
                            "scrape_batch_id": job_id,
                            "lot_size_acres": lien.get("lot_size_acres"),
                            "lot_size_sqft": lien.get("lot_size_sqft"),
                            "zoning_code": lien.get("zoning_code"),
                            "zoning_description": lien.get("zoning_description"),
                            "assessed_land_value": lien.get("assessed_land_value"),
                            "assessed_improvement_value": lien.get("assessed_improvement_value"),
                            "assessed_total_value": lien.get("assessed_total_value"),
                            "legal_description": lien.get("legal_description"),
                            "zillow_url": lien.get("zillow_url"),
                            "realtor_url": lien.get("realtor_url"),
                            "billed_amount": lien.get("billed_amount", 0),
                            "legal_class": lien.get("legal_class", ""),
                            "owner_name": lien.get("owner_name"),
                            "owner_mailing_address": lien.get("owner_mailing_address"),
                            "cfg_id": cfg["id"],
                        }
                    )
            total_saved += len(batch)
            percent = (total_saved * 100 // total_parcels) if total_parcels > 0 else 0
            print(f"[{job_id}] Progress: {total_saved}/{total_parcels} parcels saved ({percent}%)", flush=True)

        # Update config after all saves complete
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE scraper_configs SET last_run_at = NOW(), last_run_status = 'success' WHERE id = :id"),
                {"id": cfg["id"]}
            )

        print(f"[{job_id}] DONE - {total_saved} parcels saved", flush=True)

    except Exception as e:
        print(f"[{job_id}] ERROR: {e}", flush=True)
        print(traceback.format_exc(), flush=True)

# ==================== Background: Assess Thread ====================

CAPITAL_GUARDIAN_PROMPT = """### SYSTEM ROLE ###
You are the "Capital Guardian," a ruthless real estate investment risk analyst. Your ONLY goal is to prevent the loss of capital. You operate with a "Guilty until proven innocent" mindset. If a property has a red flag, you reject it immediately. You do not "hope" for appreciation; you calculate liquidation value.

### INPUT DATA ###
- Parcel ID: {parcel_id}
- Address: {address}
- State/County: {state} / {county}
- Tax Billed Amount: ${billed_amount:.2f}
- Legal Class: {legal_class}

### EXECUTION PROTOCOL ###
Process this property through these 4 logic gates in order.

GATE 1: THE KILL SWITCHES (Immediate REJECT if any are true)
Scan for these red flags:
1. "Undivided Interest" or "Percent Interest" (Must own 100% fee simple title)
2. "Common Area", "HOA", "Drainage", "Retention", "Easement", "Ingress/Egress", "Private Road" (Scrap land)
3. "Landlocked" or "No Access"
4. Lot Area < 2,500 sq ft (Unless zoned commercial)
5. Lot Width < 40 ft (Unbuildable "bowling alley" lot)
6. Prior Year Taxes > 10% of Assessed Value (Special assessments or fines)
If any kill switch triggers, output DECISION: DO NOT BID and stop.

GATE 2: THE LIQUIDITY CHECK
Calculate: Liquidation Ratio = (Total Lien Cost + $3000 Foreclosure Fees) / (Assessed Value * 0.40)
We assume fire sale = 40% of assessed value.
- IF Ratio > 1.0: REJECT (Cost exceeds fire sale value)
- IF Ratio < 1.0: PASS to Gate 3
Note: If assessed value is unknown, estimate from tax amount and legal class.

GATE 3: THE DANGER ZONES (FEMA & Environmental)
Scan for: Flood Zone A, Flood Zone AE, Wetlands, Swamp, Marsh, Superfund, Brownfield, Industrial waste.
If any found: REJECT.

GATE 4: THE SCORING MATRIX (0-100)
Start with 100 points. Deduct:
- (-20) if Outside major metro area (>30 miles)
- (-15) if Vacant Land with no utilities mentioned
- (-10) if Owner is an LLC (Sophisticated abandonment risk)
- (-30) if Property shape is "Irregular" or "Triangle"
- (-50) if "Slope" or "Steep" is detected

### REQUIRED OUTPUT FORMAT ###
You MUST respond in this exact format, one item per line:

DECISION: [BID / DO NOT BID]
RISK SCORE: [0-100]
KILL SWITCH TRIGGERED: [None / Name of specific trigger]
MAXIMUM BID: $[calculated amount]
PROPERTY TYPE: [vacant land / single-family residence / mobile home / multi-family / commercial / agricultural / other]
OWNERSHIP: [individual / LLC / trust / bank-owned / corporate / unknown]
CRITICAL WARNING: [One sentence summary of the biggest risk]"""


def _assess_thread(job_id: str, state: str, county: str, batch_size: int, max_cost: float = None):
    import httpx
    dgx_url = os.getenv("DGX_URL", "http://192.168.100.133:11434")

    cost_filter = ""
    params = {"state": state, "county": county, "batch_size": batch_size}

    if max_cost:
        cost_filter = "AND (sp.billed_amount IS NULL OR sp.billed_amount <= :max_cost)"
        params["max_cost"] = max_cost
        print(f"[{job_id}] Starting Capital Guardian assessment (batch={batch_size}, max_cost=${max_cost:,.2f})...", flush=True)
    else:
        print(f"[{job_id}] Starting Capital Guardian assessment (batch={batch_size})...", flush=True)

    try:
        # Get unassessed parcels (no row in assessments table yet)
        with engine.begin() as conn:
            parcels = conn.execute(
                text(f"""SELECT sp.id, sp.parcel_id, sp.state, sp.county, sp.address, sp.billed_amount, sp.legal_class
                        FROM scraped_parcels sp
                        LEFT JOIN assessments a ON a.parcel_id = sp.id
                        WHERE sp.state = :state AND sp.county = :county AND a.id IS NULL
                        {cost_filter}
                        ORDER BY sp.scraped_at ASC
                        LIMIT :batch_size"""),
                params
            ).mappings().all()

            if not parcels:
                print(f"[{job_id}] No unassessed parcels", flush=True)
                return

            # Create pending assessment rows
            for p in parcels:
                conn.execute(
                    text("INSERT INTO assessments (parcel_id, assessment_status) VALUES (:pid, 'assessing')"),
                    {"pid": p["id"]}
                )

        print(f"[{job_id}] Assessing {len(parcels)} parcels via Ollama...", flush=True)

        for i, parcel in enumerate(parcels):
            parcel = dict(parcel)
            sp_id = parcel["id"]

            try:
                print(f"[{job_id}] [{i+1}/{len(parcels)}] {parcel['parcel_id']}...", flush=True)

                prompt = CAPITAL_GUARDIAN_PROMPT.format(
                    parcel_id=parcel["parcel_id"],
                    address=parcel.get("address", "N/A"),
                    state=parcel.get("state", "N/A"),
                    county=parcel.get("county", "N/A"),
                    billed_amount=float(parcel.get("billed_amount") or 0),
                    legal_class=parcel.get("legal_class", "N/A"),
                )

                response = httpx.post(
                    f"{dgx_url}/api/generate",
                    json={"model": "llama3.1:8b", "prompt": prompt, "stream": False},
                    timeout=120.0,
                )
                response.raise_for_status()
                ai_text = response.json().get("response", "").strip()

                parsed = _parse_capital_guardian(ai_text)

                with engine.begin() as conn:
                    conn.execute(
                        text("""UPDATE assessments SET
                                decision = :decision, risk_score = :risk_score,
                                kill_switch = :kill_switch, max_bid = :max_bid,
                                property_type = :property_type, ownership_type = :ownership_type,
                                critical_warning = :critical_warning,
                                ai_full_response = :ai_full_response,
                                assessment_status = 'assessed', assessed_at = NOW()
                                WHERE parcel_id = :sp_id"""),
                        {
                            "decision": parsed.get("decision"),
                            "risk_score": parsed.get("risk_score"),
                            "kill_switch": parsed.get("kill_switch"),
                            "max_bid": parsed.get("max_bid"),
                            "property_type": parsed.get("property_type"),
                            "ownership_type": parsed.get("ownership_type"),
                            "critical_warning": parsed.get("critical_warning"),
                            "ai_full_response": ai_text,
                            "sp_id": sp_id,
                        }
                    )

                d = parsed.get("decision", "?")
                s = parsed.get("risk_score", "?")
                k = parsed.get("kill_switch", "None")
                print(f"[{job_id}] {parcel['parcel_id']}: {d} | Score={s} | Kill={k}", flush=True)

            except Exception as e:
                print(f"[{job_id}] FAILED {parcel['parcel_id']}: {e}", flush=True)
                with engine.begin() as conn:
                    conn.execute(
                        text("UPDATE assessments SET assessment_status='failed', assessment_error=:err WHERE parcel_id=:sp_id"),
                        {"err": str(e), "sp_id": sp_id}
                    )

            time.sleep(random.uniform(1, 3))

        print(f"[{job_id}] DONE - {len(parcels)} parcels assessed", flush=True)

    except Exception as e:
        print(f"[{job_id}] ERROR: {e}", flush=True)
        print(traceback.format_exc(), flush=True)


def _parse_capital_guardian(text: str) -> dict:
    """Parse Capital Guardian structured output."""
    result = {}

    m = re.search(r"DECISION:\s*(BID|DO NOT BID|DO_NOT_BID)", text, re.IGNORECASE)
    if m:
        val = m.group(1).strip().upper()
        result["decision"] = "BID" if val == "BID" else "DO_NOT_BID"

    m = re.search(r"RISK SCORE:\s*(\d+)", text, re.IGNORECASE)
    if m:
        result["risk_score"] = min(max(int(m.group(1)), 0), 100)

    m = re.search(r"KILL SWITCH TRIGGERED:\s*(.+)", text, re.IGNORECASE)
    if m:
        val = m.group(1).strip()
        result["kill_switch"] = None if val.lower() == "none" else val[:255]

    m = re.search(r"MAXIMUM BID:\s*\$?([\d,.]+)", text, re.IGNORECASE)
    if m:
        try:
            result["max_bid"] = float(m.group(1).replace(",", ""))
        except ValueError:
            pass

    m = re.search(r"PROPERTY TYPE:\s*(.+)", text, re.IGNORECASE)
    if m:
        result["property_type"] = m.group(1).strip()[:100]

    m = re.search(r"OWNERSHIP:\s*(.+)", text, re.IGNORECASE)
    if m:
        result["ownership_type"] = m.group(1).strip()[:100]

    m = re.search(r"CRITICAL WARNING:\s*(.+)", text, re.IGNORECASE)
    if m:
        result["critical_warning"] = m.group(1).strip()

    return result
