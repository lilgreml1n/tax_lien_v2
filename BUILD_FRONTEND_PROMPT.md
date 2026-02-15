# BUILD: Parcel Triage Web UI (React + FastAPI)

## Quick Summary

**Goal**: Build a React web interface to manually review and triage tax lien parcels

**What's Needed**:
- React frontend at localhost:3000
- New FastAPI endpoints
- Manual review checkboxes & form
- List view with filters
- Detail view with Google Maps

**Reference**: See `FRONTEND_ARCHITECTURE.md` for full details

---

## Phase 1: Backend API Endpoints (FastAPI)

### File to Modify
`backend/app/routers/scrapers.py`

### Add These 4 New Endpoints

#### Endpoint 1: Get Parcel Detail
```python
@router.get("/parcels/{parcel_id}", tags=["UI"])
def get_parcel_detail(parcel_id: int):
    """Get full parcel + assessment data for detail view"""
    with engine.connect() as conn:
        parcel = conn.execute(
            text("""SELECT sp.*, a.*
                    FROM scraped_parcels sp
                    LEFT JOIN assessments a ON a.parcel_id = sp.id
                    WHERE sp.id = :id"""),
            {"id": parcel_id}
        ).mappings().first()

    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")

    return dict(parcel)
```

#### Endpoint 2: Update Manual Review
```python
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

@router.put("/assessments/{parcel_id}", tags=["UI"])
def update_assessment(parcel_id: int, update: AssessmentUpdate):
    """Update manual review checkboxes & notes"""
    with engine.begin() as conn:
        # Check if assessment exists
        exists = conn.execute(
            text("SELECT id FROM assessments WHERE parcel_id = :pid"),
            {"pid": parcel_id}
        ).scalar()

        if not exists:
            # Create new assessment record
            conn.execute(
                text("INSERT INTO assessments (parcel_id) VALUES (:pid)"),
                {"pid": parcel_id}
            )

        # Build UPDATE statement dynamically
        updates = {}
        for field, value in update.model_dump().items():
            if value is not None:
                updates[field] = value

        if not updates:
            return {"success": True, "message": "No changes"}

        # Add timestamp
        updates["reviewed_at"] = datetime.now()

        # Build SQL
        set_clause = ", ".join([f"{k} = :{k}" for k in updates.keys()])
        query = f"UPDATE assessments SET {set_clause} WHERE parcel_id = :pid"

        conn.execute(text(query), {**updates, "pid": parcel_id})

    return {"success": True, "message": "Assessment updated"}
```

#### Endpoint 3: Search & Filter
```python
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
    """Search and filter parcels with optional full-text search"""
    query = """
        SELECT sp.id, sp.state, sp.county, sp.parcel_id, sp.owner_name,
               sp.full_address, sp.billed_amount,
               a.decision, a.risk_score, a.review_status, a.final_approved
        FROM scraped_parcels sp
        LEFT JOIN assessments a ON a.parcel_id = sp.id
        WHERE 1=1
    """
    params = {}

    if state:
        query += " AND sp.state = :state"
        params["state"] = state

    if county:
        query += " AND sp.county = :county"
        params["county"] = county

    if decision:
        query += " AND a.decision = :decision"
        params["decision"] = decision

    if review_status:
        query += " AND a.review_status = :review_status"
        params["review_status"] = review_status

    if search_term:
        query += """ AND (
            sp.parcel_id LIKE :search OR
            sp.owner_name LIKE :search OR
            sp.full_address LIKE :search
        )"""
        params["search"] = f"%{search_term}%"

    # Valid sort columns
    valid_sorts = ["id", "parcel_id", "billed_amount", "risk_score", "owner_name"]
    if sort_by not in valid_sorts:
        sort_by = "id"

    query += f" ORDER BY sp.{sort_by} DESC LIMIT :limit OFFSET :offset"
    params["limit"] = limit
    params["offset"] = offset

    with engine.connect() as conn:
        rows = conn.execute(text(query), params).mappings().all()
        total = conn.execute(
            text("""SELECT COUNT(*) FROM scraped_parcels sp
                    LEFT JOIN assessments a ON a.parcel_id = sp.id
                    WHERE 1=1""" + query.split("ORDER")[0][50:])
        ).scalar()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "parcels": [dict(row) for row in rows]
    }
```

#### Endpoint 4: Dashboard Stats
```python
@router.get("/dashboard/{state}/{county}", tags=["UI"])
def get_dashboard_stats(state: str, county: str):
    """Get summary stats for dashboard"""
    with engine.connect() as conn:
        total = conn.execute(
            text("""SELECT COUNT(*) FROM scraped_parcels
                    WHERE state = :state AND county = :county"""),
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

        rejected = conn.execute(
            text("""SELECT COUNT(*) FROM assessments a
                    JOIN scraped_parcels sp ON sp.id = a.parcel_id
                    WHERE sp.state = :state AND sp.county = :county
                    AND a.final_approved = false"""),
            {"state": state, "county": county}
        ).scalar()

    return {
        "state": state,
        "county": county,
        "total_parcels": total,
        "reviewed": reviewed,
        "approved": approved,
        "rejected": rejected,
        "pending_review": total - reviewed,
        "review_percentage": round((reviewed / total * 100) if total > 0 else 0, 1)
    }
```

---

## Phase 2: React Frontend

### Setup
```bash
npx create-react-app lienhunter-ui
cd lienhunter-ui
npm install axios react-router-dom
```

### Create Directory Structure
```
src/
├── components/
│   ├── ParcelList.tsx
│   ├── ParcelDetail.tsx
│   ├── ReviewForm.tsx
│   ├── ParcelFilters.tsx
│
├── pages/
│   ├── ListPage.tsx
│   ├── DetailPage.tsx
│
├── services/
│   ├── api.ts
│   ├── types.ts
│
├── App.tsx
├── App.css
├── index.tsx
```

### services/types.ts
```typescript
// Data types

export interface Parcel {
  id: number;
  state: string;
  county: string;
  parcel_id: string;
  owner_name: string | null;
  full_address: string | null;
  billed_amount: number | null;
  latitude: number | null;
  longitude: number | null;
  google_maps_url: string | null;
  street_view_url: string | null;
  zillow_url: string | null;
  realtor_url: string | null;
  assessed_total_value: number | null;
  legal_description: string | null;
  zoning_code: string | null;
  lot_size_acres: number | null;
}

export interface Assessment {
  id: number;
  decision: 'BID' | 'DO_NOT_BID' | null;
  risk_score: number | null;
  check_street_view: boolean;
  check_street_view_notes: string | null;
  check_power_lines: boolean;
  check_topography: boolean;
  check_topography_notes: string | null;
  check_water_test: boolean;
  check_water_notes: string | null;
  check_access_frontage: boolean;
  check_frontage_ft: number | null;
  check_rooftop_count: boolean;
  check_rooftop_pct: number | null;
  final_legal_matches_map: boolean;
  final_hidden_structure: boolean;
  final_who_cuts_grass: string | null;
  final_approved: boolean | null;
  review_status: 'pending' | 'in_review' | 'approved' | 'rejected';
  reviewer_notes: string | null;
}

export interface ParcelDetail {
  parcel: Parcel;
  assessment: Assessment | null;
}

export interface SearchResponse {
  total: number;
  parcels: Parcel[];
  limit: number;
  offset: number;
}

export interface DashboardStats {
  state: string;
  county: string;
  total_parcels: number;
  reviewed: number;
  approved: number;
  rejected: number;
  pending_review: number;
  review_percentage: number;
}
```

### services/api.ts
```typescript
import axios from 'axios';
import {
  Parcel,
  ParcelDetail,
  SearchResponse,
  DashboardStats,
  Assessment
} from './types';

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8001';

const api = axios.create({
  baseURL: API_BASE_URL
});

export const parcelAPI = {
  getDetail: (parcelId: number) =>
    api.get<ParcelDetail>(`/parcels/${parcelId}`),

  search: (params: {
    state?: string;
    county?: string;
    decision?: string;
    review_status?: string;
    search_term?: string;
    sort_by?: string;
    limit?: number;
    offset?: number;
  }) =>
    api.get<SearchResponse>('/parcels/search', { params }),

  updateAssessment: (parcelId: number, data: Partial<Assessment>) =>
    api.put(`/assessments/${parcelId}`, data),

  getDashboard: (state: string, county: string) =>
    api.get<DashboardStats>(`/dashboard/${state}/${county}`)
};
```

### components/ParcelList.tsx
```typescript
import React, { useState, useEffect } from 'react';
import { parcelAPI } from '../services/api';
import { Parcel } from '../services/types';

interface Props {
  state: string;
  county: string;
  onSelectParcel: (parcelId: number) => void;
}

export const ParcelList: React.FC<Props> = ({ state, county, onSelectParcel }) => {
  const [parcels, setParcels] = useState<Parcel[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('');

  useEffect(() => {
    const fetchParcels = async () => {
      try {
        const response = await parcelAPI.search({
          state,
          county,
          limit: 100
        });
        setParcels(response.data.parcels);
      } catch (error) {
        console.error('Failed to fetch parcels:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchParcels();
  }, [state, county]);

  if (loading) return <div>Loading...</div>;

  return (
    <div style={{ padding: '20px' }}>
      <h2>{state} / {county} - {parcels.length} Parcels</h2>

      <input
        type="text"
        placeholder="Search parcel ID, owner, address..."
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        style={{ width: '100%', padding: '10px', marginBottom: '10px' }}
      />

      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ borderBottom: '2px solid #ddd' }}>
            <th style={{ textAlign: 'left', padding: '10px' }}>Parcel ID</th>
            <th style={{ textAlign: 'left', padding: '10px' }}>Owner</th>
            <th style={{ textAlign: 'left', padding: '10px' }}>Address</th>
            <th style={{ textAlign: 'right', padding: '10px' }}>Billed Amount</th>
            <th style={{ textAlign: 'center', padding: '10px' }}>Action</th>
          </tr>
        </thead>
        <tbody>
          {parcels
            .filter(p =>
              !filter ||
              p.parcel_id.includes(filter) ||
              p.owner_name?.includes(filter) ||
              p.full_address?.includes(filter)
            )
            .map(parcel => (
              <tr key={parcel.id} style={{ borderBottom: '1px solid #eee' }}>
                <td style={{ padding: '10px' }}>{parcel.parcel_id}</td>
                <td style={{ padding: '10px' }}>{parcel.owner_name || 'N/A'}</td>
                <td style={{ padding: '10px' }}>{parcel.full_address || 'N/A'}</td>
                <td style={{ padding: '10px', textAlign: 'right' }}>
                  ${parcel.billed_amount?.toFixed(2) || '0.00'}
                </td>
                <td style={{ padding: '10px', textAlign: 'center' }}>
                  <button
                    onClick={() => onSelectParcel(parcel.id)}
                    style={{
                      padding: '5px 10px',
                      backgroundColor: '#007bff',
                      color: 'white',
                      border: 'none',
                      borderRadius: '4px',
                      cursor: 'pointer'
                    }}
                  >
                    View
                  </button>
                </td>
              </tr>
            ))}
        </tbody>
      </table>
    </div>
  );
};
```

### components/ReviewForm.tsx
```typescript
import React, { useState } from 'react';
import { Assessment } from '../services/types';
import { parcelAPI } from '../services/api';

interface Props {
  parcelId: number;
  assessment: Assessment | null;
  onSaved: () => void;
}

export const ReviewForm: React.FC<Props> = ({ parcelId, assessment, onSaved }) => {
  const [data, setData] = useState({
    check_street_view: assessment?.check_street_view || false,
    check_street_view_notes: assessment?.check_street_view_notes || '',
    check_power_lines: assessment?.check_power_lines || false,
    check_topography: assessment?.check_topography || false,
    check_topography_notes: assessment?.check_topography_notes || '',
    check_water_test: assessment?.check_water_test || false,
    check_water_notes: assessment?.check_water_notes || '',
    check_access_frontage: assessment?.check_access_frontage || false,
    check_frontage_ft: assessment?.check_frontage_ft || null,
    check_rooftop_count: assessment?.check_rooftop_count || false,
    check_rooftop_pct: assessment?.check_rooftop_pct || null,
    final_legal_matches_map: assessment?.final_legal_matches_map || false,
    final_hidden_structure: assessment?.final_hidden_structure || false,
    final_who_cuts_grass: assessment?.final_who_cuts_grass || '',
    final_approved: assessment?.final_approved || null,
    reviewer_notes: assessment?.reviewer_notes || ''
  });

  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    try {
      await parcelAPI.updateAssessment(parcelId, data);
      alert('✓ Saved successfully');
      onSaved();
    } catch (error) {
      alert('✗ Failed to save');
      console.error(error);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ padding: '20px', backgroundColor: '#f9f9f9', borderRadius: '4px' }}>
      <h3>Manual Review Checklist</h3>

      <label style={{ display: 'block', marginBottom: '10px' }}>
        <input
          type="checkbox"
          checked={data.check_street_view}
          onChange={(e) => setData({ ...data, check_street_view: e.target.checked })}
        />
        {' '}Viewed Street View
      </label>
      {data.check_street_view && (
        <textarea
          placeholder="Notes..."
          value={data.check_street_view_notes}
          onChange={(e) => setData({ ...data, check_street_view_notes: e.target.value })}
          style={{ width: '100%', marginBottom: '10px', padding: '5px' }}
        />
      )}

      <label style={{ display: 'block', marginBottom: '10px' }}>
        <input
          type="checkbox"
          checked={data.check_power_lines}
          onChange={(e) => setData({ ...data, check_power_lines: e.target.checked })}
        />
        {' '}Checked Power Lines
      </label>

      <label style={{ display: 'block', marginBottom: '10px' }}>
        <input
          type="checkbox"
          checked={data.check_topography}
          onChange={(e) => setData({ ...data, check_topography: e.target.checked })}
        />
        {' '}Checked Topography
      </label>
      {data.check_topography && (
        <textarea
          placeholder="Notes..."
          value={data.check_topography_notes}
          onChange={(e) => setData({ ...data, check_topography_notes: e.target.value })}
          style={{ width: '100%', marginBottom: '10px', padding: '5px' }}
        />
      )}

      <label style={{ display: 'block', marginBottom: '10px' }}>
        <input
          type="checkbox"
          checked={data.check_water_test}
          onChange={(e) => setData({ ...data, check_water_test: e.target.checked })}
        />
        {' '}Checked Water Access
      </label>
      {data.check_water_test && (
        <textarea
          placeholder="Notes..."
          value={data.check_water_notes}
          onChange={(e) => setData({ ...data, check_water_notes: e.target.value })}
          style={{ width: '100%', marginBottom: '10px', padding: '5px' }}
        />
      )}

      <label style={{ display: 'block', marginBottom: '10px' }}>
        <input
          type="checkbox"
          checked={data.final_legal_matches_map}
          onChange={(e) => setData({ ...data, final_legal_matches_map: e.target.checked })}
        />
        {' '}Legal Description Matches Map
      </label>

      <label style={{ display: 'block', marginBottom: '10px' }}>
        <input
          type="checkbox"
          checked={data.final_approved === true}
          onChange={(e) => setData({ ...data, final_approved: e.target.checked ? true : null })}
        />
        {' '}<strong>APPROVE</strong>
      </label>

      <textarea
        placeholder="Reviewer notes..."
        value={data.reviewer_notes}
        onChange={(e) => setData({ ...data, reviewer_notes: e.target.value })}
        style={{ width: '100%', height: '80px', marginBottom: '10px', padding: '5px' }}
      />

      <button
        onClick={handleSave}
        disabled={saving}
        style={{
          padding: '10px 20px',
          backgroundColor: '#28a745',
          color: 'white',
          border: 'none',
          borderRadius: '4px',
          cursor: 'pointer',
          fontSize: '16px'
        }}
      >
        {saving ? 'Saving...' : 'UPDATE'}
      </button>
    </div>
  );
};
```

### App.tsx
```typescript
import React, { useState } from 'react';
import { ParcelList } from './components/ParcelList';
import { ParcelDetail } from './components/ParcelDetail';

export const App: React.FC = () => {
  const [selectedParcelId, setSelectedParcelId] = useState<number | null>(null);

  return (
    <div style={{ fontFamily: 'Arial, sans-serif' }}>
      <header style={{ padding: '20px', backgroundColor: '#f0f0f0', borderBottom: '1px solid #ddd' }}>
        <h1>🏘️ Tax Lien Parcel Triage</h1>
        <p>Manually review and approve parcels for bidding</p>
      </header>

      <div style={{ display: 'flex', height: 'calc(100vh - 100px)' }}>
        <div style={{ flex: 1, overflowY: 'auto', borderRight: '1px solid #ddd' }}>
          <ParcelList
            state="Arizona"
            county="Apache"
            onSelectParcel={setSelectedParcelId}
          />
        </div>

        {selectedParcelId && (
          <div style={{ flex: 1, overflowY: 'auto' }}>
            <ParcelDetail
              parcelId={selectedParcelId}
              onClose={() => setSelectedParcelId(null)}
            />
          </div>
        )}
      </div>
    </div>
  );
};

export default App;
```

---

## What to Build (Checklist for Next Claude)

### Backend
- [ ] Add `/parcels/{parcel_id}` endpoint
- [ ] Add `/assessments/{parcel_id}` PUT endpoint
- [ ] Add `/parcels/search` endpoint
- [ ] Add `/dashboard/{state}/{county}` endpoint
- [ ] Test all endpoints with Postman/curl

### Frontend (React)
- [ ] Create project structure
- [ ] Build services/api.ts
- [ ] Build services/types.ts
- [ ] Build ParcelList component
- [ ] Build ParcelDetail component
- [ ] Build ReviewForm component
- [ ] Create App.tsx with routing
- [ ] Create .env file
- [ ] Test in browser

### Testing
- [ ] List view loads parcels
- [ ] Can filter/search parcels
- [ ] Can click parcel to view detail
- [ ] Can see parcel data and maps
- [ ] Can check review boxes
- [ ] Can click "UPDATE" and save to DB
- [ ] Database updates confirmed with MySQL query

---

## Success Criteria

✅ **Done when:**
- [ ] Frontend running at localhost:3000
- [ ] Backend API endpoints working
- [ ] List displays all parcels (state/county filter)
- [ ] Can click parcel and see detail
- [ ] Can see Google Maps link
- [ ] Can check manual review boxes
- [ ] Can save and data persists to DB
- [ ] No console errors

---

## Support Files

Check these for reference:
- `FRONTEND_ARCHITECTURE.md` - Full architecture guide
- `backend/app/routers/scrapers.py` - Existing API structure
- Database schema (provided in architecture doc)

---

**Created**: 2026-02-15
**Ready**: Yes - Send this to Claude!
