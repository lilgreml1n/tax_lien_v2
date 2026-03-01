#!/bin/bash
##############################################################################
# Check scraping and assessment progress
##############################################################################

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

STATE="${1:-Arizona}"
COUNTY="${2:-Apache}"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Progress Check: $STATE / $COUNTY${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Get counts from API
PIPELINE=$(curl -s "http://192.168.100.133:8001/scrapers/pipeline-status/$STATE/$COUNTY")

if [ -z "$PIPELINE" ]; then
    echo -e "${YELLOW}⚠️  API not responding. Is the backend running?${NC}"
    echo -e "${YELLOW}   Run: docker-compose up -d${NC}"
    exit 1
fi

# Parse JSON
SCRAPED=$(echo "$PIPELINE" | jq -r '.scraped // 0')
ASSESSED=$(echo "$PIPELINE" | jq -r '.assessed // 0')
BIDS=$(echo "$PIPELINE" | jq -r '.bids // 0')
UNASSESSED=$((SCRAPED - ASSESSED))

echo -e "${YELLOW}Scraping Progress:${NC}"
echo -e "  Total Parcels Scraped: ${GREEN}$SCRAPED${NC}"
echo ""

echo -e "${YELLOW}Assessment Progress:${NC}"
echo -e "  Assessed: ${GREEN}$ASSESSED${NC}"
echo -e "  Unassessed: ${BLUE}$UNASSESSED${NC}"
if [ $UNASSESSED -gt 0 ]; then
    PERCENT=$((ASSESSED * 100 / SCRAPED))
    echo -e "  Progress: ${GREEN}${PERCENT}%${NC} complete"
fi
echo ""

echo -e "${YELLOW}Results:${NC}"
echo -e "  BID Opportunities: ${GREEN}$BIDS${NC}"
echo -e "  Rejected: $((ASSESSED - BIDS))"
echo ""

# Check for running jobs
echo -e "${YELLOW}Active Jobs:${NC}"
LOGS=$(docker logs tax_lien_v2-backend-1 2>&1 | tail -100)

if echo "$LOGS" | grep -q "Starting scrape"; then
    LAST_SCRAPE=$(echo "$LOGS" | grep "Starting scrape" | tail -1)
    echo -e "  ${GREEN}✓${NC} Scraper running: $LAST_SCRAPE"
elif echo "$LOGS" | grep -q "DONE.*parcels saved"; then
    LAST_DONE=$(echo "$LOGS" | grep "DONE.*parcels saved" | tail -1)
    echo -e "  ${GREEN}✓${NC} Last scrape completed: $LAST_DONE"
else
    echo -e "  ${BLUE}○${NC} No active scrape job"
fi

if echo "$LOGS" | grep -q "Starting.*assessment"; then
    LAST_ASSESS=$(echo "$LOGS" | grep "Starting.*assessment" | tail -1)
    echo -e "  ${GREEN}✓${NC} Assessment running: $LAST_ASSESS"
elif echo "$LOGS" | grep -q "DONE.*parcels assessed"; then
    LAST_DONE=$(echo "$LOGS" | grep "DONE.*parcels assessed" | tail -1)
    echo -e "  ${GREEN}✓${NC} Last assessment completed: $LAST_DONE"
else
    echo -e "  ${BLUE}○${NC} No active assessment job"
fi
echo ""

# Recommendations
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}Next Steps:${NC}"
echo -e "${BLUE}========================================${NC}"

if [ $UNASSESSED -gt 0 ]; then
    echo -e "  ${YELLOW}→${NC} Resume assessment: ${BLUE}./run_scrape_assess.sh $STATE $COUNTY 0 $UNASSESSED${NC}"
fi

if [ $BIDS -gt 0 ]; then
    echo -e "  ${YELLOW}→${NC} View BID parcels: ${BLUE}./view_bids.sh${NC}"
fi

echo -e "  ${YELLOW}→${NC} View in browser: ${BLUE}http://192.168.100.133:8001/docs${NC}"
echo ""
