#!/bin/bash
##############################################################################
# Show system status and database stats
##############################################################################

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}LienHunter v2 - System Status${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Check Docker containers
echo -e "${YELLOW}Docker Containers:${NC}"
docker ps --filter "name=tax_lien_v2" --format "  {{.Names}}: {{.Status}}" | while read line; do
    if echo "$line" | grep -q "Up"; then
        echo -e "${GREEN}✓${NC} $line"
    else
        echo -e "${RED}✗${NC} $line"
    fi
done
echo ""

# Check API health
echo -e "${YELLOW}API Health:${NC}"
HEALTH=$(curl -s "http://localhost:8001/health" 2>/dev/null | jq -r '.status' || echo "error")
if [ "$HEALTH" = "ok" ]; then
    echo -e "${GREEN}✓${NC} API: http://localhost:8001 (healthy)"
else
    echo -e "${RED}✗${NC} API: Not responding"
fi
echo ""

# Database stats
echo -e "${YELLOW}Database Statistics:${NC}"
docker exec tax_lien_v2-db-1 mysql -u lienuser -plienpass lienhunter -e "
    SELECT
        COUNT(*) as total_parcels,
        COUNT(DISTINCT state) as states,
        COUNT(DISTINCT county) as counties
    FROM scraped_parcels;
" 2>/dev/null | grep -v Warning | tail -n +2 | while read total states counties; do
    echo -e "  Total Parcels: ${GREEN}$total${NC}"
    echo -e "  States: ${GREEN}$states${NC}"
    echo -e "  Counties: ${GREEN}$counties${NC}"
done

docker exec tax_lien_v2-db-1 mysql -u lienuser -plienpass lienhunter -e "
    SELECT
        COUNT(*) as total_assessments,
        SUM(CASE WHEN decision='BID' THEN 1 ELSE 0 END) as bids,
        SUM(CASE WHEN decision='DO_NOT_BID' THEN 1 ELSE 0 END) as rejects
    FROM assessments;
" 2>/dev/null | grep -v Warning | tail -n +2 | while read total bids rejects; do
    echo -e "  Assessments: ${GREEN}$total${NC}"
    echo -e "  BID: ${GREEN}$bids${NC}"
    echo -e "  DO_NOT_BID: ${RED}$rejects${NC}"
done
echo ""

# County breakdown
echo -e "${YELLOW}Parcels by County:${NC}"
docker exec tax_lien_v2-db-1 mysql -u lienuser -plienpass lienhunter -e "
    SELECT state, county, COUNT(*) as count
    FROM scraped_parcels
    GROUP BY state, county
    ORDER BY count DESC;
" 2>/dev/null | grep -v Warning | tail -n +2 | while read state county count; do
    echo -e "  $state / $county: ${GREEN}$count${NC}"
done
echo ""

echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}Quick Actions:${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "  View BIDs:       ${BLUE}./view_bids.sh${NC}"
echo -e "  Quick test:      ${BLUE}./quick_test.sh${NC}"
echo -e "  Full scrape:     ${BLUE}./scrape_all_apache.sh${NC}"
echo -e "  API docs:        ${BLUE}http://localhost:8001/docs${NC}"
echo -e "  Instructions:    ${BLUE}http://localhost:8001/instructions${NC}"
echo ""
