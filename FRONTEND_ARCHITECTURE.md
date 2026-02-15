# Parcel Triage Web UI - Architecture & Build Guide

## Overview

**Goal**: Build a React web interface to manually review and triage scraped tax lien parcels

**Tech Stack**:
- Frontend: React + TypeScript (your choice)
- Backend: FastAPI (already exists)
- Database: MySQL (already has fields!)
- Maps: Google Maps API integration

---

## Architecture Diagram

```
React Frontend (localhost:3000)
        ↓
    API Calls (HTTP)
        ↓
FastAPI Backend (localhost:8001)
        ↓
MySQL Database (tax_lien_v2-db-1)
```

---

## What We're Building

### Feature 1: Parcel List View
- Display all scraped parcels
- Show key fields: Parcel ID, Address, Owner, Billed Amount, AI Decision
- Simple filters: State, County, Decision (BID/DO_NOT_BID/Pending)
- Sortable columns

### Feature 2: Parcel Detail View
- Click a parcel to see full details
- Split screen:
  - **Left**: Parcel data (address, owner, values, legal description)
  - **Right**: Google Maps embed + Street View link
- Show AI assessment results (decision, risk score, kill switch reason)

### Feature 3: Manual Triage Checkboxes
Click on a parcel to see review form with checkboxes:

```
☐ Viewed Street View
   └─ Notes: _______________

☐ Checked Power Lines/Poles
   └─ Notes: (optional)

☐ Checked Topography
   ├─ Notes: _______________

☐ Checked Water Access
   └─ Notes: _______________

☐ Verified Access/Frontage
   └─ Frontage (feet): _____

☐ Counted Rooftops
   └─ Rooftop % count: _____

☐ Legal Description matches map
☐ Found hidden structures
☐ Identified who cuts grass: _____

[APPROVED] [REJECTED] [UPDATE BUTTON]
```

### Feature 4: Filter & Search
- Filter by: State, County, Decision, Review Status
- Search: Parcel ID, Owner Name, Address
- Sort: Parcel ID, Billed Amount, Risk Score, etc.

---

## Database Schema (Already Exists!)

### Table: `scraped_parcels`
```
- id (PK)
- state, county, parcel_id
- owner_name, owner_mailing_address
- full_address, latitude, longitude
- billed_amount
- lot_size_acres, lot_size_sqft
- zoning_code
- assessed_land_value, assessed_improvement_value, assessed_total_value
- legal_description
- google_maps_url, street_view_url, zillow_url, realtor_url
- assessor_url, treasurer_url
```

### Table: `assessments` (Manual Review Fields)
```
✅ EXISTING MANUAL REVIEW FIELDS:

- check_street_view (tinyint/boolean)
- check_street_view_notes (text)

- check_power_lines (tinyint/boolean)

- check_topography (tinyint/boolean)
- check_topography_notes (text)

- check_water_test (tinyint/boolean)
- check_water_notes (text)

- check_access_frontage (tinyint/boolean)
- check_frontage_ft (int)

- check_rooftop_count (tinyint/boolean)
- check_rooftop_pct (int)

- final_legal_matches_map (tinyint/boolean)
- final_hidden_structure (tinyint/boolean)
- final_who_cuts_grass (text)

- final_approved (tinyint/boolean)
- review_status (enum: pending, in_review, approved, rejected)
- reviewer_notes (text)
- reviewed_at (datetime)
```

---

## Backend APIs Needed

### Existing Endpoints
```
GET  /scrapers/parcels/{state}/{county}?limit=100
GET  /scrapers/unassessed/{state}/{county}
GET  /scrapers/bids?state=Arizona
GET  /scrapers/rejects?state=Arizona
```

### NEW Endpoints Needed (Build These)

#### 1. Get Parcel Detail
```
GET /parcels/{parcel_id}
Response:
{
  "parcel": { /* scraped_parcels data */ },
  "assessment": { /* assessments data */ }
}
```

#### 2. Update Manual Review
```
PUT /assessments/{parcel_id}
Body:
{
  "check_street_view": true,
  "check_street_view_notes": "Looks good, no obstructions",
  "check_power_lines": false,
  "check_topography": true,
  "check_topography_notes": "Steep slope on north side",
  "check_water_test": true,
  "check_water_notes": "Well water available",
  "check_access_frontage": true,
  "check_frontage_ft": 150,
  "check_rooftop_count": false,
  "check_rooftop_pct": null,
  "final_legal_matches_map": true,
  "final_hidden_structure": false,
  "final_who_cuts_grass": "Public roads dept",
  "final_approved": true,
  "review_status": "approved",
  "reviewer_notes": "Looks like good deal. Following up."
}
Response: { "success": true, "message": "Assessment updated" }
```

#### 3. Search & Filter
```
GET /parcels/search?
  state=Arizona&
  county=Apache&
  decision=BID&
  review_status=pending&
  search_term=smith&
  sort_by=risk_score&
  limit=50&
  offset=0

Response:
{
  "total": 123,
  "parcels": [
    {
      "id": 1,
      "parcel_id": "R0025877",
      "owner_name": "SMITH JOHN",
      "full_address": "123 Main St",
      "billed_amount": 1234.56,
      "decision": "BID",
      "risk_score": 75,
      "review_status": "pending",
      "final_approved": null
    },
    ...
  ]
}
```

#### 4. Get Statistics (Dashboard)
```
GET /dashboard/{state}/{county}
Response:
{
  "total_parcels": 500,
  "reviewed": 123,
  "approved": 45,
  "rejected": 78,
  "pending_review": 377,
  "ai_bids": 234,
  "ai_rejects": 266
}
```

---

## Frontend Structure (React)

```
src/
├── components/
│   ├── ParcelList/
│   │   ├── ParcelList.tsx       (Table view)
│   │   ├── ParcelFilters.tsx    (Filter sidebar)
│   │   ├── ParcelRow.tsx        (Single row)
│   │
│   ├── ParcelDetail/
│   │   ├── ParcelDetail.tsx     (Main detail view)
│   │   ├── ParcelData.tsx       (Left panel: data)
│   │   ├── ParcelMap.tsx        (Right panel: maps)
│   │
│   ├── ManualReview/
│   │   ├── ReviewForm.tsx       (Checkboxes & notes)
│   │   ├── ReviewCheckbox.tsx   (Single checkbox + notes)
│   │
│   ├── Common/
│   │   ├── Header.tsx
│   │   ├── Sidebar.tsx
│   │
├── pages/
│   ├── ListPage.tsx             (ParcelList + Filters)
│   ├── DetailPage.tsx           (ParcelDetail + ReviewForm)
│
├── services/
│   ├── api.ts                   (API calls)
│   ├── types.ts                 (TypeScript interfaces)
│
├── App.tsx                      (Router)
├── index.tsx
```

### Key React Components

#### 1. ParcelList Component
```typescript
// Shows table of parcels
// User clicks row to view detail
// Can filter/sort
<ParcelList
  state="Arizona"
  county="Apache"
  onRowClick={(parcel) => navigate(`/parcel/${parcel.id}`)}
/>
```

#### 2. ParcelDetail Component
```typescript
// Two-column layout
// Left: Data + Assessment
// Right: Google Maps embed
<ParcelDetail
  parcelId={1}
  onSave={(updates) => updateAssessment(updates)}
/>
```

#### 3. ReviewForm Component
```typescript
// Checkboxes for manual review
// Text fields for notes
// Approve/Reject buttons
<ReviewForm
  assessment={assessment}
  onSubmit={(data) => handleSave(data)}
/>
```

---

## Step-by-Step Build Process

### Phase 1: Setup (10 min)
- [ ] Create React app (create-react-app or Vite)
- [ ] Install dependencies: axios, react-router, tailwindcss (optional)
- [ ] Create .env with API_BASE_URL=http://localhost:8001

### Phase 2: API Integration (30 min)
- [ ] Create `services/api.ts` with all endpoint functions
- [ ] Create `services/types.ts` with TypeScript interfaces
- [ ] Test API calls manually

### Phase 3: Build Backend Endpoints (30 min)
Add to FastAPI `backend/app/routers/scrapers.py`:
- [ ] GET `/parcels/{parcel_id}` - Get detail
- [ ] PUT `/assessments/{parcel_id}` - Update review
- [ ] GET `/parcels/search` - Search/filter
- [ ] GET `/dashboard/{state}/{county}` - Stats

### Phase 4: Build Components (2-3 hours)
- [ ] ParcelList (table view)
- [ ] ParcelFilters (sidebar)
- [ ] ParcelDetail (split view)
- [ ] ReviewForm (checkboxes)
- [ ] Navigation/Router

### Phase 5: Testing (30 min)
- [ ] Test list view
- [ ] Test detail view
- [ ] Test manual review form
- [ ] Test update button saves to DB

### Phase 6: Polish (optional)
- [ ] Add styling (Tailwind/Bootstrap)
- [ ] Add pagination
- [ ] Add bulk actions
- [ ] Add export to CSV

---

## Data Flow Example

**User clicks "View Details" on parcel R0025877**

1. React router navigates to `/parcels/1`
2. ParcelDetail component loads:
   ```
   GET /parcels/1 → Backend fetches from scraped_parcels & assessments
   ```
3. Display:
   - Left: Parcel data (address, owner, values)
   - Right: Google Maps iframe + links
   - Form: Manual review checkboxes
4. User checks boxes and clicks "Save"
5. React submits:
   ```
   PUT /assessments/1
   Body: { check_street_view: true, ... }
   ```
6. Backend updates MySQL assessments table
7. UI shows "Saved ✓"

---

## React Hooks & State Management

### Simple Approach (useState/useEffect)
```typescript
// ParcelDetail.tsx
const [parcel, setParcel] = useState(null);
const [assessment, setAssessment] = useState(null);
const [loading, setLoading] = useState(true);

useEffect(() => {
  const fetchData = async () => {
    const response = await fetch(`/api/parcels/${id}`);
    const data = await response.json();
    setParcel(data.parcel);
    setAssessment(data.assessment);
    setLoading(false);
  };
  fetchData();
}, [id]);

const handleSave = async (updates) => {
  await fetch(`/api/assessments/${id}`, {
    method: 'PUT',
    body: JSON.stringify(updates)
  });
  // Refresh
};
```

### More Robust Approach (Redux/Context)
- Use Redux if you need complex state
- Or React Context for simpler needs

**Recommendation**: Start with useState, upgrade if needed

---

## Styling & UI

**Option 1: Tailwind CSS (Recommended)**
```bash
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
```

**Option 2: Material-UI**
```bash
npm install @mui/material @emotion/react @emotion/styled
```

**Option 3: Bootstrap React**
```bash
npm install react-bootstrap bootstrap
```

---

## Environment Setup

**.env file**
```
REACT_APP_API_BASE_URL=http://localhost:8001
REACT_APP_MAPS_API_KEY=your_google_maps_key
```

**Google Maps Setup**
- Get API key from https://console.cloud.google.com
- Enable Maps JavaScript API
- Embed in component: `<iframe src="https://maps.google.com/..."></iframe>`

---

## Known Gotchas

### 1. CORS Issues
**Problem**: React (localhost:3000) → FastAPI (localhost:8001)
**Solution**: FastAPI already has CORS enabled (check middleware)

### 2. Images from Maps
**Problem**: Can't embed Street View directly
**Solution**: Provide link to Street View, user opens in new tab

### 3. Large Lists
**Problem**: 2000+ parcels slow down React
**Solution**: Implement pagination or virtual scrolling

### 4. Real-time Updates
**Problem**: Don't see other users' updates live
**Solution**: Add refresh button or polling (WebSockets if needed later)

---

## Success Criteria

✅ **Complete when:**
- [ ] Frontend renders parcel list
- [ ] Can filter by state/county/decision
- [ ] Can click parcel to view detail
- [ ] Can see Google Maps embed
- [ ] Can check manual review boxes
- [ ] Can save review (updates database)
- [ ] Saved data persists when page reload
- [ ] No CORS errors

---

## Quick Reference: React Commands

```bash
# Create app
npx create-react-app lienhunter-ui
cd lienhunter-ui

# Install dependencies
npm install axios react-router-dom

# Start dev server
npm start

# Build for production
npm run build

# Note: You'll see it at localhost:3000
# FastAPI is still at localhost:8001
```

---

## Files to Create/Modify

### Backend (FastAPI)
- [ ] `backend/app/routers/scrapers.py` - Add new endpoints

### Frontend (React)
- [ ] `src/services/api.ts` - API calls
- [ ] `src/services/types.ts` - TypeScript types
- [ ] `src/components/ParcelList/ParcelList.tsx`
- [ ] `src/components/ParcelDetail/ParcelDetail.tsx`
- [ ] `src/components/ManualReview/ReviewForm.tsx`
- [ ] `src/pages/ListPage.tsx`
- [ ] `src/pages/DetailPage.tsx`
- [ ] `src/App.tsx` - Router config
- [ ] `.env` - Environment variables

---

## Next Steps

For the next Claude session, provide:
1. This architecture document
2. Current FastAPI code (routers/scrapers.py)
3. Database schema (already documented above)
4. Request: Build React UI for parcel triage

---

## Estimated Timeline

- **Phase 1-2**: 30 min (setup + API)
- **Phase 3**: 30 min (backend endpoints)
- **Phase 4**: 2-3 hours (React components)
- **Phase 5**: 30 min (testing)

**Total: 3.5-4.5 hours** for functional MVP

---

**Created**: 2026-02-15
**Status**: Ready for Claude session #2
