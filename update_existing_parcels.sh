#!/bin/bash
##############################################################################
# Update existing parcels with Google Maps URLs and county URLs
##############################################################################

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Updating Existing Parcels with URLs${NC}"
echo -e "${BLUE}========================================${NC}\n"

echo -e "${YELLOW}This will add Google Maps and county URLs to existing parcels...${NC}\n"

# Update assessor and treasurer URLs for Apache County
docker exec tax_lien_v2-db-1 mysql -u lienuser -plienpass lienhunter <<EOF 2>&1 | grep -v Warning
UPDATE scraped_parcels
SET assessor_url = CONCAT('https://eagleassessor.co.apache.az.us/assessor/taxweb/account.jsp?accountNum=', parcel_id),
    treasurer_url = CONCAT('https://eagletreasurer.co.apache.az.us:8443/treasurer/treasurerweb/account.jsp?account=', parcel_id)
WHERE state = 'Arizona' AND county = 'Apache' AND assessor_url IS NULL;
EOF

echo -e "${GREEN}✓ Updated county URLs${NC}\n"

# Build Google Maps URLs from parcel IDs for parcels without coordinates
docker exec tax_lien_v2-db-1 mysql -u lienuser -plienpass lienhunter <<EOF 2>&1 | grep -v Warning
UPDATE scraped_parcels
SET google_maps_url = CONCAT('https://www.google.com/maps/search/?api=1&query=Parcel+',
                             parcel_id, '+Apache+County+Arizona')
WHERE state = 'Arizona' AND county = 'Apache'
  AND google_maps_url IS NULL
  AND (latitude IS NULL OR longitude IS NULL);
EOF

echo -e "${GREEN}✓ Updated Google Maps URLs${NC}\n"

# Show stats
echo -e "${YELLOW}Updated Parcel Statistics:${NC}"
docker exec tax_lien_v2-db-1 mysql -u lienuser -plienpass lienhunter <<EOF 2>&1 | grep -v Warning | tail -n +2
SELECT
    COUNT(*) as total,
    SUM(CASE WHEN google_maps_url IS NOT NULL THEN 1 ELSE 0 END) as has_maps_url,
    SUM(CASE WHEN latitude IS NOT NULL THEN 1 ELSE 0 END) as has_coordinates,
    SUM(CASE WHEN assessor_url IS NOT NULL THEN 1 ELSE 0 END) as has_assessor_url
FROM scraped_parcels;
EOF

echo -e "\n${GREEN}✓ All existing parcels updated!${NC}"
echo -e "${BLUE}Test: http://localhost:8001/scrapers/parcels/Arizona/Apache?limit=5${NC}\n"
