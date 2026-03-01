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

# ==================== Helpers ====================

def _is_job_alive(job_id: str, timeout_seconds: int = 300) -> bool:
    """Check if a job is truly running by looking for recent activity in Docker logs.

    Returns True if the job has produced output in the last `timeout_seconds`.
    Returns False if job appears dead/stuck.
    """
    try:
        import subprocess
        # Get last 200 lines of Docker logs
        result = subprocess.run(
            ["docker", "logs", "tax_lien_v2-backend-1"],
            capture_output=True,
            text=True,
            timeout=10
        )
        logs = result.stderr + result.stdout

        # Look for recent job output (within timeout window)
        now = time.time()
        for line in logs.split('\n')[-200:]:  # Check last 200 lines
            if job_id in line:
                # Found recent activity for this job
                return True

        # No recent activity found
        return False
    except Exception as e:
        print(f"[_is_job_alive] Error checking logs: {e}", flush=True)
        # On error, assume it's not alive to allow restart
        return False

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

class AssessmentUpdate(BaseModel):
    check_street_view: Optional[bool] = None
    check_street_view_notes: Optional[str] = None
    check_power_lines: Optional[bool] = None
    check_topography: Optional[bool] = None
    check_topography_notes: Optional[str] = None
    check_water_test: Optional[bool] = None
    check_water_notes: Optional[str] = None
    check_access_frontage: Optional[bool] = None
    check_frontage_ft: Optional[int] = None
    check_rooftop_count: Optional[bool] = None
    check_rooftop_pct: Optional[int] = None
    final_legal_matches_map: Optional[bool] = None
    final_hidden_structure: Optional[bool] = None
    final_who_cuts_grass: Optional[str] = None
    final_approved: Optional[bool] = None
    review_status: Optional[str] = None
    reviewer_notes: Optional[str] = None

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
def scrape(state: str, county: str, limit: int = 10, resume: bool = False):
    """Phase 1: Scrape parcels from county website. Saves raw data to DB. No AI.

    Args:
        state: State name
        county: County name
        limit: Max parcels to scrape (0 = all)
        resume: If True, resume from last checkpoint instead of starting over
    """
    with engine.connect() as conn:
        cfg = conn.execute(
            text("SELECT * FROM scraper_configs WHERE state = :state AND county = :county"),
            {"state": state, "county": county}
        ).mappings().first()
    if not cfg:
        raise HTTPException(status_code=404, detail=f"No scraper configured for {state}/{county}")

    # Block if a scrape is already running for this state/county
    with engine.connect() as conn:
        checkpoint = conn.execute(
            text("SELECT last_page_completed, total_parcels_scraped, status, job_id FROM scraper_checkpoints WHERE state = :state AND county = :county"),
            {"state": state, "county": county}
        ).mappings().first()

    if checkpoint and checkpoint["status"] == "in_progress":
        # Job claims to be in_progress — verify it's actually alive by checking logs
        job_id = checkpoint["job_id"]
        is_alive = _is_job_alive(job_id)

        if is_alive:
            # Job is truly running
            raise HTTPException(
                status_code=409,
                detail=f"Scrape already in_progress for {state}/{county} (job: {job_id}, page {checkpoint['last_page_completed']}). Still running. Use GET /scrapers/checkpoint to check status."
            )
        else:
            # Job claims in_progress but shows no activity — mark as failed so we can restart
            print(f"[{state}/{county}] Job {job_id} was in_progress but not alive. Marking as failed to allow restart.", flush=True)
            with engine.begin() as conn:
                conn.execute(
                    text("UPDATE scraper_checkpoints SET status = 'failed' WHERE state = :state AND county = :county"),
                    {"state": state, "county": county}
                )
            # Fall through to start new job

    cfg_dict = dict(cfg)
    job_id = f"scrape_{state}_{county}_{int(datetime.now().timestamp())}"

    # Determine start page from checkpoint
    start_page = 1
    if resume and checkpoint and checkpoint["status"] == "failed":
        start_page = checkpoint["last_page_completed"] + 1
        print(f"[{job_id}] Resuming from page {start_page} ({checkpoint['total_parcels_scraped']} parcels already scraped)", flush=True)

    t = threading.Thread(target=_scrape_thread, args=(job_id, state, county, cfg_dict, limit, start_page), daemon=True)
    t.start()

    status_msg = "scraping"
    if resume and start_page > 1:
        status_msg = f"resuming from page {start_page}"

    return JobOut(job_id=job_id, status=status_msg, started_at=datetime.now().isoformat())


@router.get("/checkpoint/{state}/{county}", tags=["Scrapers", "Scrape"])
def get_checkpoint(state: str, county: str):
    """Get the current scrape checkpoint for a county."""
    with engine.connect() as conn:
        checkpoint = conn.execute(
            text("SELECT * FROM scraper_checkpoints WHERE state = :state AND county = :county"),
            {"state": state, "county": county}
        ).mappings().first()
    if not checkpoint:
        return {"state": state, "county": county, "last_page_completed": 0, "total_parcels_scraped": 0, "status": "none"}
    return dict(checkpoint)

# ==================== Phase 2: Assess ====================

@router.post("/assess/{state}/{county}", response_model=JobOut, tags=["Scrapers", "Assess"])
def assess(state: str, county: str, batch_size: int = 10, max_cost: float = None, resume: bool = False):
    """Phase 2: Run Capital Guardian AI on unassessed parcels via DGX Ollama.

    Args:
        state: State name
        county: County name
        batch_size: Number of parcels per batch
        max_cost: Optional max billed amount to assess. Skip more expensive parcels.
                 Example: max_cost=5000 only assesses parcels with billed_amount <= $5,000
        resume: If True, reset stuck 'assessing' parcels to retry them
    """

    # Check if assessment already running for this county
    with engine.connect() as conn:
        running_assessments = conn.execute(
            text("""SELECT COUNT(*) FROM assessments a
                    JOIN scraped_parcels sp ON sp.id = a.parcel_id
                    WHERE sp.state = :state AND sp.county = :county
                    AND a.assessment_status = 'assessing'"""),
            {"state": state, "county": county}
        ).scalar()

    if running_assessments > 0 and not resume:
        # Check if it's actually alive
        # Use a simple heuristic: if there are parcels in 'assessing' state, assume it's stuck
        # (since normal runs should complete or fail, not leave parcels hanging)
        print(f"[{state}/{county}] Found {running_assessments} parcels in 'assessing' state. Assuming previous job crashed.", flush=True)
        if not resume:
            raise HTTPException(
                status_code=409,
                detail=f"Assessment appears stuck for {state}/{county} ({running_assessments} parcels in 'assessing'). Use /assess?resume=true to reset and restart."
            )

    # If resume=True, reset stuck 'assessing' parcels
    if resume:
        with engine.begin() as conn:
            reset_count = conn.execute(
                text("""UPDATE assessments a
                        JOIN scraped_parcels sp ON sp.id = a.parcel_id
                        SET a.assessment_status = 'pending'
                        WHERE sp.state = :state AND sp.county = :county
                        AND a.assessment_status = 'assessing'"""),
                {"state": state, "county": county}
            ).rowcount
            if reset_count > 0:
                print(f"[Resume] Reset {reset_count} stuck 'assessing' parcels to 'pending'", flush=True)
    with engine.connect() as conn:
        # Build query with optional cost filter (include NULL and 'pending' status)
        if max_cost:
            query = """SELECT COUNT(*) FROM scraped_parcels sp
                    LEFT JOIN assessments a ON a.parcel_id = sp.id
                    WHERE sp.state = :state AND sp.county = :county
                    AND (a.id IS NULL OR a.assessment_status = 'pending')
                    AND (sp.billed_amount IS NULL OR sp.billed_amount <= :max_cost)"""
            params = {"state": state, "county": county, "max_cost": max_cost}
        else:
            query = """SELECT COUNT(*) FROM scraped_parcels sp
                    LEFT JOIN assessments a ON a.parcel_id = sp.id
                    WHERE sp.state = :state AND sp.county = :county
                    AND (a.id IS NULL OR a.assessment_status = 'pending')"""
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

# NOTE: /parcels/detail and /parcels/search MUST be defined before /parcels/{state}/{county}
# or FastAPI will match "detail" and "search" as the {state} parameter.

@router.get("/parcels/detail/{parcel_id}", tags=["UI"])
def get_parcel_detail(parcel_id: int):
    """Get full parcel + assessment data for detail view."""
    with engine.connect() as conn:
        parcel = conn.execute(
            text("""SELECT sp.*, a.id as assessment_id, a.decision, a.risk_score,
                           a.kill_switch, a.max_bid, a.property_type, a.ownership_type,
                           a.critical_warning, a.assessment_status, a.review_status,
                           a.check_street_view, a.check_street_view_notes,
                           a.check_power_lines, a.check_topography, a.check_topography_notes,
                           a.check_water_test, a.check_water_notes,
                           a.check_access_frontage, a.check_frontage_ft,
                           a.check_rooftop_count, a.check_rooftop_pct,
                           a.final_legal_matches_map, a.final_hidden_structure,
                           a.final_who_cuts_grass, a.final_approved,
                           a.reviewer_notes, a.reviewed_at
                    FROM scraped_parcels sp
                    LEFT JOIN assessments a ON a.parcel_id = sp.id
                    WHERE sp.id = :id"""),
            {"id": parcel_id}
        ).mappings().first()

    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")

    return dict(parcel)


@router.get("/parcels/search", tags=["UI"])
def search_parcels(
    state: Optional[str] = None,
    county: Optional[str] = None,
    decision: Optional[str] = None,
    review_status: Optional[str] = None,
    search_term: Optional[str] = None,
    sort_by: str = "id",
    limit: int = 50,
    offset: int = 0
):
    """Search and filter parcels."""
    where_clauses = []
    params = {}

    if state:
        where_clauses.append("sp.state = :state")
        params["state"] = state
    if county:
        where_clauses.append("sp.county = :county")
        params["county"] = county
    if decision:
        where_clauses.append("a.decision = :decision")
        params["decision"] = decision
    if review_status:
        where_clauses.append("a.review_status = :review_status")
        params["review_status"] = review_status
    if search_term:
        where_clauses.append("""(
            sp.parcel_id LIKE :search OR
            sp.owner_name LIKE :search OR
            sp.full_address LIKE :search
        )""")
        params["search"] = f"%{search_term}%"

    where_sql = (" AND ".join(where_clauses)) if where_clauses else "1=1"

    valid_sorts = ["id", "parcel_id", "billed_amount", "risk_score", "owner_name"]
    if sort_by not in valid_sorts:
        sort_by = "id"

    sort_col = f"a.{sort_by}" if sort_by == "risk_score" else f"sp.{sort_by}"

    query = f"""SELECT sp.id, sp.state, sp.county, sp.parcel_id, sp.owner_name,
                       sp.full_address, sp.billed_amount,
                       a.decision, a.risk_score, a.review_status, a.final_approved,
                       a.property_type
                FROM scraped_parcels sp
                LEFT JOIN assessments a ON a.parcel_id = sp.id
                WHERE {where_sql}
                ORDER BY {sort_col} DESC
                LIMIT :limit OFFSET :offset"""
    params["limit"] = limit
    params["offset"] = offset

    count_query = f"""SELECT COUNT(*) FROM scraped_parcels sp
                      LEFT JOIN assessments a ON a.parcel_id = sp.id
                      WHERE {where_sql}"""

    with engine.connect() as conn:
        rows = conn.execute(text(query), params).mappings().all()
        total = conn.execute(text(count_query), {k: v for k, v in params.items() if k not in ("limit", "offset")}).scalar()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "parcels": [dict(row) for row in rows]
    }


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

# ==================== Phase 3: Backfill ====================

@router.post("/backfill/{state}/{county}", response_model=JobOut, tags=["Scrapers", "Backfill"])
def backfill(state: str, county: str, bids_only: bool = True):
    """Phase 3: Re-hit assessor/GIS/treasurer to fill missing data on already-scraped parcels.

    Fills in: owner_name, owner_mailing_address, latitude, longitude, full_address
    (reverse geocoded), assessed values, lot size, legal class, legal description,
    years_delinquent, prior_liens_count, total_outstanding, first_delinquent_year,
    google_maps_url, street_view_url.

    Uses COALESCE — never overwrites existing data. Safe to re-run at any time.

    Args:
        bids_only: If True (default), only backfill parcels where Capital Guardian said BID,
                   prioritized by risk score. If False, backfill ALL parcels missing key data.
    """
    from app.backfill_bids import COUNTY_REGISTRY
    if (state, county) not in COUNTY_REGISTRY:
        supported = ", ".join(f"{s}/{c}" for s, c in COUNTY_REGISTRY)
        raise HTTPException(status_code=400, detail=f"Backfill not configured for {state}/{county}. Supported: {supported}. Add an entry to COUNTY_REGISTRY in backfill_bids.py.")

    job_id = f"backfill_{state}_{county}_{int(datetime.now().timestamp())}"

    t = threading.Thread(
        target=_backfill_thread,
        args=(job_id, state, county, bids_only),
        daemon=True
    )
    t.start()

    label = "BID parcels only" if bids_only else "all parcels missing data"
    return JobOut(job_id=job_id, status=f"backfilling ({label})", started_at=datetime.now().isoformat())


def _backfill_thread(job_id: str, state: str, county: str, bids_only: bool):
    """Run backfill_bids.py logic in a background thread."""
    import asyncio
    import sys

    print(f"[{job_id}] Starting backfill for {state}/{county} (bids_only={bids_only})...", flush=True)
    try:
        sys.path.insert(0, '/app')
        from app.backfill_bids import backfill as run_backfill
        loop = asyncio.new_event_loop()
        loop.run_until_complete(run_backfill(bids_only=bids_only, county_key=(state, county)))
        loop.close()
        print(f"[{job_id}] Backfill complete.", flush=True)
    except Exception as e:
        import traceback
        print(f"[{job_id}] Backfill ERROR: {e}", flush=True)
        traceback.print_exc()


# ==================== UI Endpoints ====================

@router.put("/assessments/{parcel_id}", tags=["UI"])
def update_assessment(parcel_id: int, update: AssessmentUpdate):
    """Update manual review checkboxes & notes."""
    with engine.begin() as conn:
        exists = conn.execute(
            text("SELECT id FROM assessments WHERE parcel_id = :pid"),
            {"pid": parcel_id}
        ).scalar()

        if not exists:
            conn.execute(
                text("INSERT INTO assessments (parcel_id) VALUES (:pid)"),
                {"pid": parcel_id}
            )

        updates = {}
        for field, value in update.model_dump().items():
            if value is not None:
                updates[field] = value

        if not updates:
            return {"success": True, "message": "No changes"}

        updates["reviewed_at"] = datetime.now()
        set_clause = ", ".join([f"{k} = :{k}" for k in updates.keys()])
        query = f"UPDATE assessments SET {set_clause} WHERE parcel_id = :pid"
        conn.execute(text(query), {**updates, "pid": parcel_id})

    return {"success": True, "message": "Assessment updated"}


@router.get("/dashboard/{state}/{county}", tags=["UI"])
def get_dashboard_stats(state: str, county: str):
    """Get summary stats for dashboard."""
    with engine.connect() as conn:
        total = conn.execute(
            text("SELECT COUNT(*) FROM scraped_parcels WHERE state = :state AND county = :county"),
            {"state": state, "county": county}
        ).scalar()

        assessed = conn.execute(
            text("""SELECT COUNT(*) FROM assessments a
                    JOIN scraped_parcels sp ON sp.id = a.parcel_id
                    WHERE sp.state = :state AND sp.county = :county
                    AND a.assessment_status = 'assessed'"""),
            {"state": state, "county": county}
        ).scalar()

        bids = conn.execute(
            text("""SELECT COUNT(*) FROM assessments a
                    JOIN scraped_parcels sp ON sp.id = a.parcel_id
                    WHERE sp.state = :state AND sp.county = :county
                    AND a.decision = 'BID'"""),
            {"state": state, "county": county}
        ).scalar()

        reviewed = conn.execute(
            text("""SELECT COUNT(*) FROM assessments a
                    JOIN scraped_parcels sp ON sp.id = a.parcel_id
                    WHERE sp.state = :state AND sp.county = :county
                    AND a.final_approved IS NOT NULL"""),
            {"state": state, "county": county}
        ).scalar()

        approved = conn.execute(
            text("""SELECT COUNT(*) FROM assessments a
                    JOIN scraped_parcels sp ON sp.id = a.parcel_id
                    WHERE sp.state = :state AND sp.county = :county
                    AND a.final_approved = true"""),
            {"state": state, "county": county}
        ).scalar()

    return {
        "state": state,
        "county": county,
        "total_parcels": total,
        "assessed": assessed,
        "bids": bids,
        "reviewed": reviewed,
        "approved": approved,
        "pending_review": total - reviewed,
    }

# ==================== Background: Scrape Thread ====================

SCRAPER_REGISTRY = {
    "app.scrapers.arizona.apache.ApacheScraper": None,
    "app.scrapers.arizona.coconino.CoconinaScraper": None,
    "app.scrapers.arizona.yavapai.YavapaiScraper": None,
    "app.scrapers.arizona.mohave.MohaveScraper": None,
    "app.scrapers.nebraska.douglas.DouglasScraper": None,
    "app.scrapers.nebraska.lancaster.LancasterScraper": None,
    "app.scrapers.nebraska.sarpy.SarpyScraper": None,
    "app.scrapers.nebraska.saline.SalineScraper": None,
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

def _save_parcels_and_checkpoint(job_id: str, state: str, county: str, cfg_id: int,
                                  liens: list, page: int):
    """Save a page of parcels to DB and update the checkpoint."""
    with engine.begin() as conn:
        for lien in liens:
            conn.execute(
                text("""INSERT IGNORE INTO scraped_parcels
                        (state, county, parcel_id, address, latitude, longitude, full_address,
                         google_maps_url, street_view_url, assessor_url, treasurer_url,
                         source_url, auction_url, scrape_batch_id,
                         lot_size_acres, lot_size_sqft, zoning_code, zoning_description,
                         assessed_land_value, assessed_improvement_value, assessed_total_value,
                         legal_description, zillow_url, realtor_url,
                         billed_amount, legal_class, owner_name, owner_mailing_address,
                         years_delinquent, prior_liens_count, total_outstanding, first_delinquent_year,
                         scraper_config_id)
                        VALUES (:state, :county, :parcel_id, :address, :latitude, :longitude, :full_address,
                                :google_maps_url, :street_view_url, :assessor_url, :treasurer_url,
                                :source_url, :auction_url, :scrape_batch_id,
                                :lot_size_acres, :lot_size_sqft, :zoning_code, :zoning_description,
                                :assessed_land_value, :assessed_improvement_value, :assessed_total_value,
                                :legal_description, :zillow_url, :realtor_url,
                                :billed_amount, :legal_class, :owner_name, :owner_mailing_address,
                                :years_delinquent, :prior_liens_count, :total_outstanding, :first_delinquent_year,
                                :cfg_id)"""),
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
                    "years_delinquent": lien.get("years_delinquent"),
                    "prior_liens_count": lien.get("prior_liens_count"),
                    "total_outstanding": lien.get("total_outstanding"),
                    "first_delinquent_year": lien.get("first_delinquent_year"),
                    "cfg_id": cfg_id,
                }
            )

        # Update checkpoint
        conn.execute(
            text("""INSERT INTO scraper_checkpoints (state, county, last_page_completed, total_parcels_scraped, job_id, status)
                    VALUES (:state, :county, :page, :count, :job_id, 'in_progress')
                    ON DUPLICATE KEY UPDATE
                        last_page_completed = :page,
                        total_parcels_scraped = total_parcels_scraped + :count,
                        job_id = :job_id,
                        status = 'in_progress'"""),
            {"state": state, "county": county, "page": page, "count": len(liens), "job_id": job_id}
        )

    print(f"[{job_id}] Page {page}: saved {len(liens)} parcels, checkpoint updated", flush=True)


def _scrape_thread(job_id: str, state: str, county: str, cfg: dict, limit: int, start_page: int = 1):
    import asyncio
    print(f"[{job_id}] Starting scrape (limit={limit}, start_page={start_page})...", flush=True)

    try:
        scraper_class = _get_scraper_class(cfg["scraper_name"])
        if not scraper_class:
            print(f"[{job_id}] Scraper class not found: {cfg['scraper_name']}", flush=True)
            return

        # Initialize checkpoint for fresh starts
        if start_page == 1:
            with engine.begin() as conn:
                conn.execute(
                    text("""INSERT INTO scraper_checkpoints (state, county, last_page_completed, total_parcels_scraped, job_id, status)
                            VALUES (:state, :county, 0, 0, :job_id, 'in_progress')
                            ON DUPLICATE KEY UPDATE
                                last_page_completed = 0,
                                total_parcels_scraped = 0,
                                job_id = :job_id,
                                status = 'in_progress'"""),
                    {"state": state, "county": county, "job_id": job_id}
                )

        # Callback that saves each page's parcels immediately
        _notify_counter = [0]
        def on_page_complete(page_liens, page_num):
            _save_parcels_and_checkpoint(job_id, state, county, cfg["id"], page_liens, page_num)
            _notify_counter[0] += len(page_liens)
            if _notify_counter[0] >= 100:
                _notify_counter[0] = 0
                from app.discord_notify import post_status
                post_status(state, county)

        loop = asyncio.new_event_loop()
        scraper = scraper_class(state, county)
        liens = loop.run_until_complete(
            scraper.scrape(limit=limit, start_page=start_page, on_page_complete=on_page_complete)
        )
        loop.close()

        total_saved = len(liens)

        # Mark checkpoint as completed (include total_parcels_available if the scraper set it)
        total_available = getattr(scraper, "total_parcels_available", 0)
        with engine.begin() as conn:
            conn.execute(
                text("""UPDATE scraper_checkpoints
                        SET status = 'completed',
                            total_parcels_available = CASE WHEN :total > 0 THEN :total ELSE total_parcels_available END
                        WHERE state = :state AND county = :county"""),
                {"state": state, "county": county, "total": total_available}
            )
            conn.execute(
                text("UPDATE scraper_configs SET last_run_at = NOW(), last_run_status = 'success' WHERE id = :id"),
                {"id": cfg["id"]}
            )

        print(f"[{job_id}] DONE - {total_saved} parcels saved (total available: {total_available or 'unknown'})", flush=True)
        from app.discord_notify import post_status
        post_status(state, county, note="✅ Scrape complete!")

    except Exception as e:
        # Mark checkpoint as failed so resume knows to pick up
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE scraper_checkpoints SET status = 'failed' WHERE state = :state AND county = :county"),
                {"state": state, "county": county}
            )
        print(f"[{job_id}] ERROR: {e}", flush=True)
        print(traceback.format_exc(), flush=True)

# ==================== Background: Assess Thread ====================

CAPITAL_GUARDIAN_PROMPT = """You are the "Capital Guardian." This parcel passed preliminary screening. Your job: score it.

### PARCEL DATA ###
Parcel: {parcel_id} | {address} | {state}/{county}
Billed: ${billed_amount:.2f} | Legal Class: {legal_class} | Lot: {lot_size} | Zoning: {zoning}
Assessed - Land: {assessed_land} | Improvement: {assessed_improvement} | Total: {assessed_total}
Legal Description: {legal_desc}
Owner: {owner_name} | Mailing: {owner_mail}

### TAX PAYMENT HISTORY ###
Years delinquent: {years_delinquent}
Prior tax lien sales on this parcel: {prior_liens_count}
Total outstanding (all years): {total_outstanding}
First delinquent year: {first_delinquent_year}

### CONTEXT (pre-computed) ###
- Liquidity check (Gate 2): {gate2_result}
- Estate/Heirs owner: {estate_flag}
- Absentee owner (mailing≠property): {mailing_differs}
- Equity ratio (assessed/billed<10x): {equity_flag}

### YOUR SCORING TASK (Gate 4) ###
Start at 100. Adjustments:
- Deduct 20: clearly rural, >30 miles from any city
- Deduct 15: vacant land (no improvement)
- Deduct 10: owner is LLC or Corp
- Deduct 10: equity_flag starts with "YES"
- Deduct 15: years_delinquent >= 5 (chronic non-payer, high total redemption cost)
- Deduct 25: prior_liens_count >= 3 (land sold at tax sale multiple times = abandonment pattern)
- Add 15: estate_flag is "YES"
- Add 10: mailing_differs is "YES"
Cap final score at 100.

### OUTPUT FORMAT - respond ONLY in this exact format ###
DECISION: [BID / DO NOT BID]
RISK SCORE: [0-100]
KILL SWITCH TRIGGERED: [None / reason if Gate 2 failed]
MAXIMUM BID: $[billed_amount * 1.1 if BID, else 0]
PROPERTY TYPE: [vacant land / single-family / mobile home / multi-family / commercial / agricultural / other]
OWNERSHIP: [individual / LLC / trust / estate / corporate / unknown]
CRITICAL WARNING: [one sentence about the biggest risk or opportunity]"""


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
        # Get unassessed parcels (no row in assessments table yet OR status='pending')
        with engine.begin() as conn:
            parcels = conn.execute(
                text(f"""SELECT sp.id, sp.parcel_id, sp.state, sp.county,
                                sp.address, sp.full_address, sp.billed_amount, sp.legal_class,
                                sp.lot_size_acres, sp.lot_size_sqft,
                                sp.zoning_code, sp.zoning_description,
                                sp.assessed_land_value, sp.assessed_improvement_value, sp.assessed_total_value,
                                sp.legal_description,
                                sp.owner_name, sp.owner_mailing_address,
                                sp.years_delinquent, sp.prior_liens_count, sp.total_outstanding, sp.first_delinquent_year
                        FROM scraped_parcels sp
                        LEFT JOIN assessments a ON a.parcel_id = sp.id
                        WHERE sp.state = :state AND sp.county = :county
                        AND (a.id IS NULL OR a.assessment_status = 'pending')
                        {cost_filter}
                        ORDER BY sp.scraped_at ASC
                        LIMIT :batch_size"""),
                params
            ).mappings().all()

            if not parcels:
                print(f"[{job_id}] No unassessed parcels", flush=True)
                return

            # Create or update to 'assessing' status
            for p in parcels:
                conn.execute(
                    text("""INSERT INTO assessments (parcel_id, assessment_status)
                            VALUES (:pid, 'assessing')
                            ON DUPLICATE KEY UPDATE assessment_status = 'assessing'"""),
                    {"pid": p["id"]}
                )

        print(f"[{job_id}] Assessing {len(parcels)} parcels via Ollama...", flush=True)

        assessed_count = 0
        for i, parcel in enumerate(parcels):
            parcel = dict(parcel)
            sp_id = parcel["id"]

            try:
                print(f"[{job_id}] [{i+1}/{len(parcels)}] {parcel['parcel_id']}...", flush=True)

                billed = float(parcel.get("billed_amount") or 0)
                raw_improvement = parcel.get("assessed_improvement_value")
                raw_total = parcel.get("assessed_total_value")
                assessed_improvement = float(raw_improvement) if raw_improvement is not None else None
                assessed_total = float(raw_total) if raw_total is not None else None
                owner_name = parcel.get("owner_name") or "Unknown"
                owner_mail = parcel.get("owner_mailing_address") or ""
                prop_addr = parcel.get("full_address") or parcel.get("address") or ""

                # --- Gate 1: Fully computed in Python (no LLM involvement) ---
                # Rule: unknown/N/A data = skip that check (benefit of doubt)
                legal_desc = (parcel.get("legal_description") or "")
                combined_text = (owner_name + " " + legal_desc).upper()

                gate1_trigger = None  # None = PASS, string = REJECT reason

                # Check 1: Bankruptcy / IRS
                if not gate1_trigger:
                    for kw in ["BANKRUPTCY", "INTERNAL REVENUE", "UNITED STATES GOVT", "FEDERAL TAX LIEN"]:
                        if kw in combined_text:
                            gate1_trigger = f"Bankruptcy/IRS: {kw}"
                            break

                # Check 2: Shack (only if improvement value is a known number)
                if not gate1_trigger and assessed_improvement is not None and assessed_improvement < 10000:
                    gate1_trigger = f"Likely shack: improvement value ${assessed_improvement:,.0f}"

                # Check 3: Lot too small (only if sqft is a known number)
                raw_sqft = parcel.get("lot_size_sqft")
                if not gate1_trigger and raw_sqft is not None and int(raw_sqft) < 2500:
                    gate1_trigger = f"Lot too small: {int(raw_sqft):,} sqft"

                # Check 4: Legal description + environmental keywords
                if not gate1_trigger:
                    LEGAL_DESC_KILLS = [
                        "UNDIVIDED INTEREST", "PERCENT INTEREST", "COMMON AREA",
                        "HOMEOWNERS ASSOCIATION", " HOA ", "DRAINAGE EASEMENT",
                        "RETENTION BASIN", "PRIVATE ROAD EASEMENT", "LANDLOCKED",
                        "NO ACCESS", "INGRESS/EGRESS EASEMENT",
                        "FLOOD ZONE A", "FLOOD ZONE AE", "WETLAND", "SWAMP", "MARSH",
                        "SUPERFUND", "BROWNFIELD",
                    ]
                    for kw in LEGAL_DESC_KILLS:
                        if kw in legal_desc.upper():
                            gate1_trigger = f"Legal desc: {kw}"
                            break

                # Gate 1 result
                gate1_result = "REJECTED" if gate1_trigger else "PASSED"

                # --- Gate 2: Liquidity check in Python ---
                gate2_result = "SKIPPED (assessed value unknown)"
                if assessed_total is not None and assessed_total > 0:
                    liq_ratio = (billed + 3000) / (assessed_total * 0.40)
                    if liq_ratio > 1.0:
                        if not gate1_trigger:
                            gate1_trigger = f"Liquidity ratio {liq_ratio:.2f} > 1.0"
                            gate1_result = "REJECTED"
                        gate2_result = f"FAILED: ratio={liq_ratio:.2f}"
                    else:
                        gate2_result = f"PASSED: ratio={liq_ratio:.2f}"

                # --- Scoring signals for LLM (Gate 4) ---
                # These feed into LLM scoring only
                estate_flag = "YES" if any(kw in owner_name.upper() for kw in
                    ["ESTATE OF", "HEIRS OF"]) else "NO"
                mailing_differs = "YES" if (owner_mail and prop_addr and
                    owner_mail.strip().lower()[:30] != prop_addr.strip().lower()[:30]) else "NO"
                if assessed_total is not None and assessed_total > 0 and billed > 0:
                    equity_ratio = assessed_total / billed
                    equity_flag = f"YES ({equity_ratio:.1f}x ratio)" if equity_ratio < 10 else f"NO ({equity_ratio:.1f}x ratio)"
                else:
                    equity_flag = "UNKNOWN"

                # Short-circuit: if Gate 1 rejected in Python, skip the LLM entirely
                if gate1_result == "REJECTED":
                    # Derive property type from legal class
                    lc = (parcel.get("legal_class") or "").upper()
                    if "R" in lc or "RESIDENTIAL" in lc:
                        prop_type = "single-family"
                    elif "V" in lc or "VACANT" in lc:
                        prop_type = "vacant land"
                    else:
                        prop_type = "unknown"

                    with engine.begin() as conn:
                        conn.execute(
                            text("""UPDATE assessments SET
                                    decision = 'DO_NOT_BID', risk_score = 0,
                                    kill_switch = :kill, max_bid = 0,
                                    property_type = :ptype, ownership_type = 'unknown',
                                    critical_warning = :kill,
                                    ai_full_response = :resp,
                                    assessment_status = 'assessed', assessed_at = NOW()
                                    WHERE parcel_id = :sp_id"""),
                            {
                                "kill": gate1_trigger[:255],
                                "ptype": prop_type,
                                "resp": f"[Gate 1 rejected by Python] {gate1_trigger}",
                                "sp_id": sp_id,
                            }
                        )
                    print(f"[{job_id}] {parcel['parcel_id']}: DO_NOT_BID | Score=0 | Kill={gate1_trigger} [no LLM needed]", flush=True)
                    assessed_count += 1
                    if assessed_count % 10 == 0:
                        pct = int((assessed_count / len(parcels)) * 100)
                        print(f"[{job_id}] Progress: {assessed_count}/{len(parcels)} ({pct}%)", flush=True)
                    continue  # Skip LLM call

                yrs_delinquent = parcel.get("years_delinquent")
                prior_liens = parcel.get("prior_liens_count")
                total_owed = parcel.get("total_outstanding")
                first_delinquent = parcel.get("first_delinquent_year")

                prompt = CAPITAL_GUARDIAN_PROMPT.format(
                    parcel_id=parcel["parcel_id"],
                    address=prop_addr or "N/A",
                    state=parcel.get("state", "N/A"),
                    county=parcel.get("county", "N/A"),
                    billed_amount=billed,
                    legal_class=parcel.get("legal_class", "N/A"),
                    lot_size=f"{parcel.get('lot_size_acres') or 'N/A'} acres",
                    zoning=f"{parcel.get('zoning_code') or 'N/A'} {parcel.get('zoning_description') or ''}".strip(),
                    assessed_land=f"${parcel.get('assessed_land_value'):,.0f}" if parcel.get("assessed_land_value") else "N/A",
                    assessed_improvement=f"${assessed_improvement:,.0f}" if assessed_improvement is not None else "N/A",
                    assessed_total=f"${assessed_total:,.0f}" if assessed_total is not None else "N/A",
                    legal_desc=legal_desc[:500] or "N/A",
                    owner_name=owner_name,
                    owner_mail=owner_mail or "N/A",
                    years_delinquent=str(yrs_delinquent) if yrs_delinquent is not None else "unknown",
                    prior_liens_count=str(prior_liens) if prior_liens is not None else "unknown",
                    total_outstanding=f"${float(total_owed):,.2f}" if total_owed is not None else "unknown",
                    first_delinquent_year=str(first_delinquent) if first_delinquent is not None else "unknown",
                    gate2_result=gate2_result,
                    estate_flag=estate_flag,
                    mailing_differs=mailing_differs,
                    equity_flag=equity_flag,
                )

                response = httpx.post(
                    f"{dgx_url}/api/generate",
                    json={"model": "llama3.1:70b", "prompt": prompt, "stream": False},
                    timeout=180.0,
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

                assessed_count += 1

                # Progress checkpoint every 10 parcels
                if assessed_count % 10 == 0:
                    pct = int((assessed_count / len(parcels)) * 100)
                    print(f"[{job_id}] Progress: {assessed_count}/{len(parcels)} parcels assessed ({pct}%)", flush=True)

            except Exception as e:
                print(f"[{job_id}] FAILED {parcel['parcel_id']}: {e}", flush=True)
                with engine.begin() as conn:
                    conn.execute(
                        text("UPDATE assessments SET assessment_status='failed', assessment_error=:err WHERE parcel_id=:sp_id"),
                        {"err": str(e), "sp_id": sp_id}
                    )

            time.sleep(random.uniform(1, 3))

        # Final summary with decision counts
        with engine.connect() as conn:
            stats = conn.execute(
                text("""SELECT decision, COUNT(*) as cnt
                        FROM assessments a
                        JOIN scraped_parcels sp ON sp.id = a.parcel_id
                        WHERE sp.state = :state AND sp.county = :county
                        GROUP BY decision"""),
                {"state": state, "county": county}
            ).mappings().all()

            bid_count = sum(s["cnt"] for s in stats if s["decision"] == "BID")
            reject_count = sum(s["cnt"] for s in stats if s["decision"] == "DO_NOT_BID")

        print(f"[{job_id}] DONE - {len(parcels)} parcels assessed | BID: {bid_count} | DO_NOT_BID: {reject_count}", flush=True)
        from app.discord_notify import post_status
        post_status(state, county, note=f"✅ Assessment batch complete — {bid_count} BID, {reject_count} DO_NOT_BID")

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
