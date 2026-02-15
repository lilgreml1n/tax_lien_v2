from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from app.database import engine

router = APIRouter(prefix="/review", tags=["Review"])


class ChecklistUpdate(BaseModel):
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
    reviewer_notes: Optional[str] = None


class FinalApproval(BaseModel):
    final_legal_matches_map: Optional[bool] = None
    final_hidden_structure: Optional[bool] = None
    final_who_cuts_grass: Optional[str] = None
    reviewer_notes: Optional[str] = None


@router.get("/queue", tags=["Review"])
def review_queue(state: Optional[str] = None, limit: int = 50):
    """Get BID parcels that need human Google Earth review."""
    query = """SELECT sp.parcel_id, sp.state, sp.county, sp.address, sp.billed_amount,
                      a.id as assessment_id, a.risk_score, a.max_bid, a.property_type,
                      a.critical_warning, a.review_status,
                      a.check_street_view, a.check_power_lines, a.check_topography,
                      a.check_water_test, a.check_access_frontage, a.check_rooftop_count
               FROM assessments a
               JOIN scraped_parcels sp ON sp.id = a.parcel_id
               WHERE a.decision = 'BID' AND a.review_status IN ('pending', 'in_review')"""
    params = {}
    if state:
        query += " AND sp.state = :state"
        params["state"] = state
    query += " ORDER BY a.risk_score DESC LIMIT :limit"
    params["limit"] = limit
    with engine.connect() as conn:
        rows = conn.execute(text(query), params).mappings().all()
    return rows


@router.put("/checklist/{assessment_id}", tags=["Review"])
def update_checklist(assessment_id: int, data: ChecklistUpdate):
    """Update human visual checklist (Google Earth review) for a parcel."""
    with engine.begin() as conn:
        row = conn.execute(text("SELECT id FROM assessments WHERE id = :id"), {"id": assessment_id}).first()
        if not row:
            raise HTTPException(status_code=404, detail="Assessment not found")

        updates = ["review_status = 'in_review'"]
        params = {"id": assessment_id}

        for field, value in data.model_dump(exclude_none=True).items():
            updates.append(f"{field} = :{field}")
            params[field] = value

        conn.execute(text(f"UPDATE assessments SET {', '.join(updates)} WHERE id = :id"), params)

    return {"status": "updated", "assessment_id": assessment_id}


@router.put("/final-approve/{assessment_id}", tags=["Review"])
def final_approve(assessment_id: int, data: FinalApproval):
    """Final Boss approval - last check before purchasing the lien."""
    with engine.begin() as conn:
        row = conn.execute(text("SELECT id FROM assessments WHERE id = :id"), {"id": assessment_id}).first()
        if not row:
            raise HTTPException(status_code=404, detail="Assessment not found")

        updates = ["reviewed_at = NOW()"]
        params = {"id": assessment_id}

        for field, value in data.model_dump(exclude_none=True).items():
            updates.append(f"{field} = :{field}")
            params[field] = value

        # Auto-approve if legal matches and no hidden structure
        if data.final_legal_matches_map and data.final_hidden_structure is False:
            updates.append("final_approved = 1")
            updates.append("review_status = 'approved'")
        else:
            updates.append("final_approved = 0")

        conn.execute(text(f"UPDATE assessments SET {', '.join(updates)} WHERE id = :id"), params)

    return {"status": "reviewed", "assessment_id": assessment_id}


@router.get("/approved", tags=["Review"])
def get_approved(limit: int = 50):
    """Get all parcels that passed every gate - ready to buy."""
    with engine.connect() as conn:
        rows = conn.execute(
            text("""SELECT sp.parcel_id, sp.state, sp.county, sp.address, sp.billed_amount,
                           a.risk_score, a.max_bid, a.property_type, a.critical_warning,
                           a.reviewed_at, a.reviewer_notes
                    FROM assessments a
                    JOIN scraped_parcels sp ON sp.id = a.parcel_id
                    WHERE a.final_approved = 1
                    ORDER BY a.reviewed_at DESC
                    LIMIT :limit"""),
            {"limit": limit}
        ).mappings().all()
    return rows
