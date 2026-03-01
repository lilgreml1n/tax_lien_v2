#!/bin/bash

##############################################################################
# LienHunter v2 - Scrape Only
#
# Usage:
#   ./scrape.sh <state> <county> [limit]
#
# Examples:
#   ./scrape.sh Arizona Apache          # Scrape all (0 = unlimited)
#   ./scrape.sh Arizona Apache 200      # Scrape 200 parcels only
#   ./scrape.sh Arizona Coconino 100    # Scrape 100 Coconino parcels
##############################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

API_URL="http://192.168.100.133:8001"

# Parse arguments
STATE="${1:-Arizona}"
COUNTY="${2:-Apache}"
LIMIT="${3:-0}"  # 0 = scrape all

# Validate inputs
if [ -z "$STATE" ] || [ -z "$COUNTY" ]; then
    echo -e "${RED}Usage: ./scrape.sh <state> <county> [limit]${NC}"
    echo -e "Example: ./scrape.sh Arizona Apache 200"
    exit 1
fi

# Lock file to prevent concurrent scrapes of same county
LOCK_FILE="/tmp/lienhunter_${STATE}_${COUNTY}.lock"

# Check if another scrape is already running
if [ -f "$LOCK_FILE" ]; then
    LOCK_PID=$(cat "$LOCK_FILE")
    if ps -p "$LOCK_PID" > /dev/null 2>&1; then
        echo -e "${RED}✗ Another scrape is already running for $STATE/$COUNTY (PID: $LOCK_PID)${NC}"
        echo -e "${YELLOW}  Wait for it to finish, or kill it with: kill $LOCK_PID${NC}"
        exit 1
    else
        rm -f "$LOCK_FILE"
    fi
fi

# Create lock file with current PID
echo $$ > "$LOCK_FILE"
trap "rm -f $LOCK_FILE" EXIT

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}LienHunter v2 - Scrape Only${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "State:          ${GREEN}$STATE${NC}"
echo -e "County:         ${GREEN}$COUNTY${NC}"
if [ "$LIMIT" = "0" ]; then
    echo -e "Limit:          ${GREEN}All parcels (0 = unlimited)${NC}"
else
    echo -e "Limit:          ${GREEN}$LIMIT parcels${NC}"
fi
echo -e "${BLUE}========================================${NC}"
echo -e "${YELLOW}⏱️  Using human-like delays (2-8s)${NC}"
echo -e "   to avoid detection. Be patient!${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Step 1: Check API health
echo -e "${YELLOW}[1/3] Checking API health...${NC}"
HEALTH=$(curl -s "$API_URL/health" | jq -r '.status' 2>/dev/null || echo "error")
if [ "$HEALTH" = "ok" ]; then
    echo -e "${GREEN}✓ API is healthy${NC}\n"
else
    echo -e "${RED}✗ API is not responding. Is the backend running?${NC}"
    echo -e "${YELLOW}Run: docker-compose up -d${NC}"
    exit 1
fi

# Step 2: Start scrape
echo -e "${YELLOW}[2/3] Starting scrape job...${NC}"
SCRAPE_RESPONSE=$(curl -s -X POST "$API_URL/scrapers/scrape/$STATE/$COUNTY?limit=$LIMIT")
JOB_ID=$(echo "$SCRAPE_RESPONSE" | jq -r '.job_id')

if [ "$JOB_ID" = "null" ] || [ -z "$JOB_ID" ]; then
    echo -e "${RED}✗ Failed to start scrape job${NC}"
    echo "Response: $SCRAPE_RESPONSE"
    exit 1
fi

echo -e "${GREEN}✓ Scrape job started: $JOB_ID${NC}"
echo -e "${BLUE}Waiting for scrape to complete...${NC}\n"

# Step 3: Wait for scrape to finish
WAIT_TIME=0
LAST_PAGE=0
NO_PROGRESS_COUNT=0
MAX_NO_PROGRESS=15  # 15 minutes with no new pages = timeout

while true; do
    sleep 60  # Check every minute
    WAIT_TIME=$((WAIT_TIME + 60))

    # Check backend logs for completion
    LOGS=$(docker logs tax_lien_v2-backend-1 2>&1 | tail -100)

    if echo "$LOGS" | grep -q "\[$JOB_ID\] DONE"; then
        # Extract parcel count from completion message
        PARCEL_COUNT=$(echo "$LOGS" | grep "\[$JOB_ID\] DONE" | tail -1 | grep -oE "[0-9]+ parcels" | grep -oE "[0-9]+")
        echo -e "\n${GREEN}✓ Scrape completed!${NC}"
        echo -e "${GREEN}✓ Total parcels saved: $PARCEL_COUNT${NC}\n"
        break
    fi

    # Check current page number
    CURRENT_PAGE=$(echo "$LOGS" | grep -oE "Fetching page [0-9]+" | tail -1 | grep -oE "[0-9]+")

    if [ -z "$CURRENT_PAGE" ]; then
        # No page found, still initializing
        echo -ne "${BLUE}  Initializing... ${WAIT_TIME}s elapsed\r${NC}"
    elif [ "$CURRENT_PAGE" -gt "$LAST_PAGE" ]; then
        # Making progress!
        LAST_PAGE=$CURRENT_PAGE
        NO_PROGRESS_COUNT=0
        echo -ne "${BLUE}  Scraping page $CURRENT_PAGE... ${WAIT_TIME}s elapsed (~$((WAIT_TIME / 60)) min) [Human delays active]\r${NC}"
    else
        # No progress detected (processing parcels on current page with human-like delays)
        NO_PROGRESS_COUNT=$((NO_PROGRESS_COUNT + 1))
        echo -ne "${YELLOW}  Page $CURRENT_PAGE... ${WAIT_TIME}s elapsed (processing with delays: $NO_PROGRESS_COUNT/$MAX_NO_PROGRESS)\r${NC}"

        if [ $NO_PROGRESS_COUNT -ge $MAX_NO_PROGRESS ]; then
            echo -e "\n${RED}✗ Scraper appears stuck. Check logs:${NC}"
            echo -e "${YELLOW}  docker logs tax_lien_v2-backend-1 -f | grep '\[$JOB_ID\]'${NC}"
            exit 1
        fi
    fi
done

# Step 4: Show results summary
echo -e "${YELLOW}[3/3] Fetching scrape results...${NC}"
RESULTS=$(curl -s "$API_URL/scrapers/parcels/$STATE/$COUNTY?limit=10")
TOTAL=$(echo "$RESULTS" | jq 'length')

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}SCRAPE COMPLETE - $STATE / $COUNTY${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "Total parcels saved:  ${GREEN}$TOTAL${NC}"
echo -e "Next step:            ${BLUE}./assess.sh $STATE $COUNTY${NC}"
echo -e "${BLUE}========================================${NC}\n"
