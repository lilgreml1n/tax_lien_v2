# GIS & Mapping Features

## Overview

Every parcel now includes clickable links to:
- 🗺️ Google Maps
- 🏛️ County Assessor page
- 💰 County Treasurer page

Plus GIS coordinates (when available from county website).

---

## Database Fields

### New Fields in `scraped_parcels` Table

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `latitude` | DECIMAL(10,7) | GIS latitude coordinate | 34.5678901 |
| `longitude` | DECIMAL(10,7) | GIS longitude coordinate | -109.1234567 |
| `full_address` | TEXT | Complete property address | "123 Main St, St Johns, AZ 85936" |
| `google_maps_url` | VARCHAR(500) | Clickable Google Maps link | https://www.google.com/maps/... |
| `assessor_url` | VARCHAR(500) | County assessor property page | https://eagleassessor.co.apache.az.us/... |
| `treasurer_url` | VARCHAR(500) | County treasurer tax page | https://eagletreasurer.co.apache.az.us/... |

---

## How Google Maps URLs Work

### Priority 1: GIS Coordinates (Most Accurate)
If scraper finds lat/lon coordinates:
```
https://www.google.com/maps/search/?api=1&query=34.567890,-109.123456
```
✓ Pinpoints exact location on map

### Priority 2: Full Address
If address available but no coordinates:
```
https://www.google.com/maps/search/?api=1&query=123+Main+St+St+Johns+AZ
```
✓ Google geocodes the address

### Priority 3: Parcel ID Search
Fallback when only parcel ID available:
```
https://www.google.com/maps/search/?api=1&query=Parcel+R0106010+Apache+County+Arizona
```
✓ May find parcel in Google's database

---

## API Examples

### Get Parcels with Mapping Data
```bash
GET /scrapers/parcels/Arizona/Apache?limit=10
```

**Response includes:**
```json
{
  "parcel_id": "R0106010",
  "full_address": "123 Main St, Apache County, AZ",
  "latitude": 34.5678901,
  "longitude": -109.1234567,
  "google_maps_url": "https://www.google.com/maps/search/?api=1&query=34.5678901,-109.1234567",
  "assessor_url": "https://eagleassessor.co.apache.az.us/assessor/taxweb/account.jsp?accountNum=R0106010",
  "treasurer_url": "https://eagletreasurer.co.apache.az.us:8443/treasurer/treasurerweb/account.jsp?account=R0106010",
  "billed_amount": 3254.98,
  "decision": "DO_NOT_BID",
  ...
}
```

---

## Frontend Integration

### Simple HTML Table
```html
<table>
  <tr>
    <td>{{ parcel_id }}</td>
    <td><a href="{{ google_maps_url }}" target="_blank">📍 View Map</a></td>
    <td><a href="{{ assessor_url }}" target="_blank">🏛️ Assessor</a></td>
    <td><a href="{{ treasurer_url }}" target="_blank">💰 Treasurer</a></td>
  </tr>
</table>
```

### React/Vue Component
```jsx
<a href={parcel.google_maps_url} target="_blank" rel="noopener">
  📍 View on Google Maps
</a>
```

---

## Scraper Implementation

The Apache County scraper now:

1. **Extracts address** from assessor page
   - Looks for "Situs Address", "Property Address", "Physical Location"
   - Multiple regex patterns for robustness

2. **Searches for GIS coordinates**
   - Checks for `latitude`, `longitude` fields
   - Validates coordinates are in Arizona range (31-37°N, 109-115°W)
   - Falls back to address if no coords found

3. **Builds URLs automatically**
   - Google Maps: from coords > address > parcel ID
   - Assessor: parcel-specific URL
   - Treasurer: parcel-specific URL
   - All saved to database

---

## Update Existing Parcels

Already scraped parcels? Run this script to add URLs:

```bash
./update_existing_parcels.sh
```

**What it does:**
- Adds assessor/treasurer URLs to all Apache County parcels
- Builds Google Maps URLs from parcel IDs (fallback method)
- Shows statistics of updated records

---

## Testing

### View a Parcel in Browser
```bash
# Get parcel data
curl "http://localhost:8001/scrapers/parcels/Arizona/Apache?limit=1" | jq '.[0]'

# Copy google_maps_url and open in browser
```

### Database Query
```sql
SELECT parcel_id, google_maps_url, full_address, latitude, longitude
FROM scraped_parcels
WHERE state = 'Arizona' AND county = 'Apache'
LIMIT 10;
```

---

## Future Enhancements

### County-Specific GIS APIs
Some counties provide GIS APIs with:
- Property boundaries (polygons)
- Aerial imagery URLs
- Tax maps
- Zoning information

### Geocoding Service
For parcels without coordinates, use geocoding service:
- Google Geocoding API
- USGS Geocoding Service
- County GIS servers

### Embedded Maps
Add iframe maps directly in frontend:
```html
<iframe
  src="https://www.google.com/maps/embed/v1/place?key=YOUR_KEY&q=34.567,-109.123"
  width="400" height="300">
</iframe>
```

---

## Troubleshooting

**No coordinates found:**
- County may not publish GIS data on public pages
- May require GIS API access or FOIA request
- Google Maps URL from parcel ID still works

**Google Maps shows wrong location:**
- Parcel ID search relies on Google's database
- May show county office instead of property
- Solution: Get actual address or coordinates

**URLs don't work:**
- County may have changed website structure
- Update scraper URL patterns
- Test with recent parcels

---

**Questions?** Check `/docs` or view source code in `backend/app/scrapers/arizona/apache.py`
