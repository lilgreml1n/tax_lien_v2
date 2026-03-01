#!/bin/bash
##############################################################################
# Scrape Mohave County parcels — auto-resumes if a previous run was interrupted
#
# Usage:
#   ./scrape_all_mohave.sh        # Scrape all parcels (resumes if interrupted)
#   ./scrape_all_mohave.sh 5      # Quick test — 5 parcels
#   ./scrape_all_mohave.sh 100    # Scrape 100 parcels
##############################################################################

cd "$(dirname "$0")"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

API_URL="http://localhost:8001"
LIMIT="${1:-0}"

# Check for an existing checkpoint
CHECKPOINT=$(curl -s "$API_URL/scrapers/checkpoint/Arizona/Mohave")
STATUS=$(echo "$CHECKPOINT" | jq -r '.status')
LAST_PAGE=$(echo "$CHECKPOINT" | jq -r '.last_page_completed')
TOTAL_SO_FAR=$(echo "$CHECKPOINT" | jq -r '.total_parcels_scraped')

RESUME_PARAM=""

if [ "$STATUS" = "failed" ] || [ "$STATUS" = "in_progress" ]; then
    RESUME_PARAM="&resume=true"
    echo -e "${YELLOW}Previous run found (status: $STATUS)${NC}"
    echo -e "  Parcels scraped so far: ${GREEN}$TOTAL_SO_FAR${NC}"
    echo -e "  Resuming from row:      ${GREEN}$(( LAST_PAGE * 50 ))${NC}"
    echo ""
else
    if [ "$LIMIT" = "0" ]; then
        echo -e "Starting fresh — scraping ${GREEN}ALL${NC} Mohave County parcels"
        echo -e "${YELLOW}Warning: This may take several hours with human-like delays${NC}"
    else
        echo -e "Starting fresh — scraping ${GREEN}$LIMIT${NC} Mohave County parcels"
    fi
    echo ""
fi

read -p "Continue? (y/n) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

# Start (or resume) the scrape job
SCRAPE_RESPONSE=$(curl -s -X POST "$API_URL/scrapers/scrape/Arizona/Mohave?limit=$LIMIT$RESUME_PARAM")
JOB_ID=$(echo "$SCRAPE_RESPONSE" | jq -r '.job_id')

if [ "$JOB_ID" = "null" ] || [ -z "$JOB_ID" ]; then
    echo -e "${RED}Failed to start scrape. Response:${NC}"
    echo "$SCRAPE_RESPONSE"
    exit 1
fi

echo -e "${GREEN}Job started: $JOB_ID${NC}"
echo -e "Following logs... (Ctrl+C to detach — scrape keeps running in Docker)\n"

# Follow logs until this job completes or errors
docker logs tax_lien_v2-backend-1 -f 2>&1 | while IFS= read -r line; do
    echo "$line"
    if echo "$line" | grep -q "\[$JOB_ID\] DONE"; then
        echo -e "\n${GREEN}Scrape complete!${NC}"
        echo -e "Next step: ${BLUE}./assess.sh Arizona Mohave${NC}"
        pkill -P $$ docker 2>/dev/null
        break
    fi
    if echo "$line" | grep -q "\[$JOB_ID\] ERROR"; then
        echo -e "\n${YELLOW}Scrape stopped with an error — run the script again to resume.${NC}"
        pkill -P $$ docker 2>/dev/null
        break
    fi
done
