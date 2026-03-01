#!/bin/bash

##############################################################################
# LienHunter v2 - Automated Scrape & Assess Script
#
# Usage:
#   ./run_scrape_assess.sh <state> <county> <scrape_limit> <assess_batch> [resume]
#
# Examples:
#   ./run_scrape_assess.sh Arizona Apache 50 50           # Fresh start
#   ./run_scrape_assess.sh Arizona Apache 0 100           # 0 = scrape ALL
#   ./run_scrape_assess.sh Arizona Apache 0 100 resume    # Resume from checkpoint
##############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

API_URL="http://localhost:8001"

# Parse arguments
STATE="${1:-Arizona}"
COUNTY="${2:-Apache}"
SCRAPE_LIMIT="${3:-50}"
ASSESS_BATCH="${4:-50}"
RESUME="${5:-}"

# Lock file to prevent concurrent runs
LOCK_FILE="/tmp/lienhunter_${STATE}_${COUNTY}.lock"

# Check if another instance is running
if [ -f "$LOCK_FILE" ]; then
    LOCK_PID=$(cat "$LOCK_FILE")
    if ps -p "$LOCK_PID" > /dev/null 2>&1; then
        echo -e "${RED}✗ Another scrape is already running for $STATE/$COUNTY (PID: $LOCK_PID)${NC}"
        echo -e "${YELLOW}  Wait for it to finish, or kill it with: kill $LOCK_PID${NC}"
        exit 1
    else
        # Stale lock file, remove it
        rm -f "$LOCK_FILE"
    fi
fi

# Check for active scrape jobs (only recent logs to avoid false positives)
RECENT_LOGS=$(docker logs tax_lien_v2-backend-1 2>&1 | tail -500)
STARTED_JOBS=$(echo "$RECENT_LOGS" | grep -oE "scrape_${STATE}_${COUNTY}_[0-9]+" | sort -u)
for JOB in $STARTED_JOBS; do
    if ! echo "$RECENT_LOGS" | grep -q "\[$JOB\] DONE"; then
        echo -e "${RED}✗ Scrape job '$JOB' is already running in the background${NC}"
        echo -e "${YELLOW}  Check progress: docker logs tax_lien_v2-backend-1 -f | grep 'Fetching page'${NC}"
        echo -e "${YELLOW}  Or restart backend to kill it: docker-compose restart backend${NC}"
        exit 1
    fi
done

# Create lock file with current PID
echo $$ > "$LOCK_FILE"

# Remove lock file on exit (success or failure)
trap "rm -f $LOCK_FILE" EXIT

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}LienHunter v2 - Automated Pipeline${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "State:          ${GREEN}$STATE${NC}"
echo -e "County:         ${GREEN}$COUNTY${NC}"
echo -e "Scrape Limit:   ${GREEN}$SCRAPE_LIMIT${NC} (0 = all parcels)"
echo -e "Assess Batch:   ${GREEN}$ASSESS_BATCH${NC}"
if [ "$RESUME" = "resume" ]; then
    echo -e "Mode:           ${YELLOW}RESUME (picking up where we left off)${NC}"
else
    echo -e "Mode:           ${GREEN}Fresh start${NC}"
fi
echo -e "${BLUE}========================================${NC}"
echo -e "${YELLOW}⏱️  Scraper uses human-like delays (2-8s)"
echo -e "   to avoid detection. This is normal!${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Step 1: Check API health
echo -e "${YELLOW}[1/5] Checking API health...${NC}"
HEALTH=$(curl -s "$API_URL/health" | jq -r '.status' 2>/dev/null || echo "error")
if [ "$HEALTH" = "ok" ]; then
    echo -e "${GREEN}✓ API is healthy${NC}\n"
else
    echo -e "${RED}✗ API is not responding. Is the backend running?${NC}"
    echo -e "${YELLOW}Run: docker-compose up -d${NC}"
    exit 1
fi

# Step 2: Check checkpoint (if resuming)
if [ "$RESUME" = "resume" ]; then
    echo -e "${YELLOW}[2/5] Checking checkpoint...${NC}"
    CHECKPOINT=$(curl -s "$API_URL/scrapers/checkpoint/$STATE/$COUNTY")
    LAST_PAGE=$(echo "$CHECKPOINT" | jq -r '.last_page_completed')
    ALREADY_SCRAPED=$(echo "$CHECKPOINT" | jq -r '.total_parcels_scraped')
    CP_STATUS=$(echo "$CHECKPOINT" | jq -r '.status')
    if [ "$LAST_PAGE" != "0" ] && [ "$CP_STATUS" != "completed" ]; then
        echo -e "${GREEN}✓ Checkpoint found: page $LAST_PAGE, $ALREADY_SCRAPED parcels already scraped${NC}"
        echo -e "${BLUE}  Will resume from page $((LAST_PAGE + 1))${NC}\n"
    else
        echo -e "${YELLOW}  No checkpoint to resume from, starting fresh${NC}\n"
    fi
    SCRAPE_RESPONSE=$(curl -s -X POST "$API_URL/scrapers/scrape/$STATE/$COUNTY?limit=$SCRAPE_LIMIT&resume=true")
else
    echo -e "${YELLOW}[2/5] Starting scrape...${NC}"
    SCRAPE_RESPONSE=$(curl -s -X POST "$API_URL/scrapers/scrape/$STATE/$COUNTY?limit=$SCRAPE_LIMIT")
fi
JOB_ID=$(echo "$SCRAPE_RESPONSE" | jq -r '.job_id')
echo -e "${GREEN}✓ Scrape job started: $JOB_ID${NC}"
echo -e "${BLUE}Waiting for scrape to complete...${NC}"

# Wait for scrape to finish (smart progress checking)
WAIT_TIME=0
LAST_PAGE=0
NO_PROGRESS_COUNT=0
MAX_NO_PROGRESS=15  # Exit if no progress for 15 checks (15 minutes) - allows time for human-like delays

while true; do
    sleep 60  # Check every minute
    WAIT_TIME=$((WAIT_TIME + 60))

    # Check backend logs for completion
    LOGS=$(docker logs tax_lien_v2-backend-1 2>&1 | tail -100)
    if echo "$LOGS" | grep -q "DONE.*parcels saved"; then
        echo -e "\n${GREEN}✓ Scrape completed!${NC}\n"
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
            echo -e "\n${RED}✗ Scraper appears stuck. Check logs: docker logs tax_lien_v2-backend-1${NC}"
            exit 1
        fi
    fi
done

# Step 3: Check how many need assessment
echo -e "${YELLOW}[3/5] Checking unassessed parcels...${NC}"
UNASSESSED=$(curl -s "$API_URL/scrapers/unassessed/$STATE/$COUNTY" | jq -r '.unassessed_count')
echo -e "${GREEN}✓ Found $UNASSESSED parcels needing assessment${NC}\n"

if [ "$UNASSESSED" = "0" ]; then
    echo -e "${YELLOW}No parcels to assess. Showing results...${NC}\n"
else
    # Step 4: Trigger assessment
    echo -e "${YELLOW}[4/5] Starting AI assessment (DGX Ollama)...${NC}"
    ASSESS_RESPONSE=$(curl -s -X POST "$API_URL/scrapers/assess/$STATE/$COUNTY?batch_size=$ASSESS_BATCH")
    ASSESS_JOB=$(echo "$ASSESS_RESPONSE" | jq -r '.job_id')
    echo -e "${GREEN}✓ Assessment job started: $ASSESS_JOB${NC}"
    echo -e "${BLUE}Waiting for assessment to complete...${NC}"
    echo -e "${YELLOW}  (This takes ~6-10 seconds per parcel)${NC}"

    # Wait for assessment (smart progress checking)
    WAIT_TIME=0
    LAST_COUNT=0
    NO_PROGRESS_COUNT=0
    MAX_NO_PROGRESS=3  # Exit if no progress for 3 checks (3 minutes)

    while true; do
        sleep 60  # Check every minute
        WAIT_TIME=$((WAIT_TIME + 60))

        # Check for completion
        LOGS=$(docker logs tax_lien_v2-backend-1 2>&1 | tail -100)
        if echo "$LOGS" | grep -q "DONE.*parcels assessed"; then
            echo -e "\n${GREEN}✓ Assessment completed!${NC}\n"
            break
        fi

        # Count how many parcels have been assessed so far
        CURRENT_COUNT=$(echo "$LOGS" | grep -oE "\[[0-9]+/$ASSESS_BATCH\]" | tail -1 | grep -oE "^[0-9]+" | tr -d '[')

        if [ -z "$CURRENT_COUNT" ]; then
            CURRENT_COUNT=0
        fi

        if [ "$CURRENT_COUNT" -gt "$LAST_COUNT" ]; then
            # Making progress!
            LAST_COUNT=$CURRENT_COUNT
            NO_PROGRESS_COUNT=0
            echo -ne "${BLUE}  Assessed $CURRENT_COUNT/$ASSESS_BATCH... ${WAIT_TIME}s elapsed (~$((WAIT_TIME / 60)) min)\r${NC}"
        else
            # No progress detected
            NO_PROGRESS_COUNT=$((NO_PROGRESS_COUNT + 1))
            echo -ne "${YELLOW}  Assessing... ${WAIT_TIME}s elapsed (no progress: $NO_PROGRESS_COUNT/3)\r${NC}"

            if [ $NO_PROGRESS_COUNT -ge $MAX_NO_PROGRESS ]; then
                echo -e "\n${RED}✗ Assessment appears stuck. Check logs: docker logs tax_lien_v2-backend-1${NC}"
                exit 1
            fi
        fi
    done
fi

# Step 5: Show results
echo -e "${YELLOW}[5/5] Fetching results...${NC}"
RESULTS=$(curl -s "$API_URL/scrapers/parcels/$STATE/$COUNTY?limit=100")

TOTAL=$(echo "$RESULTS" | jq 'length')
BIDS=$(echo "$RESULTS" | jq '[.[] | select(.decision == "BID")] | length')
REJECTS=$(echo "$RESULTS" | jq '[.[] | select(.decision == "DO_NOT_BID")] | length')
PENDING=$(echo "$RESULTS" | jq '[.[] | select(.decision == null)] | length')

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}RESULTS - $STATE / $COUNTY${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "Total Parcels:     ${GREEN}$TOTAL${NC}"
echo -e "✓ BID:             ${GREEN}$BIDS${NC}"
echo -e "✗ DO_NOT_BID:      ${RED}$REJECTS${NC}"
echo -e "⏳ Pending:        ${YELLOW}$PENDING${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Show sample BID parcels if any
if [ "$BIDS" -gt 0 ]; then
    echo -e "${GREEN}Investment Opportunities (BID):${NC}"
    echo "$RESULTS" | jq -r '
        [.[] | select(.decision == "BID")] |
        .[] |
        "  Parcel: \(.parcel_id) | Billed: $\(.billed_amount) | Score: \(.risk_score) | Type: \(.property_type)"
    '
    echo ""
fi

# Show sample rejects
echo -e "${RED}Top Rejection Reasons:${NC}"
echo "$RESULTS" | jq -r '
    [.[] | select(.decision == "DO_NOT_BID")] |
    group_by(.kill_switch) |
    sort_by(-length) |
    .[:5] |
    .[] |
    "  [\(length)] \(.[0].kill_switch)"
'

echo -e "\n${BLUE}========================================${NC}"
echo -e "${GREEN}✓ Pipeline complete!${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "\nView full results:"
echo -e "  Browser: ${BLUE}http://localhost:8001/docs${NC}"
echo -e "  All:     ${BLUE}GET /scrapers/parcels/$STATE/$COUNTY${NC}"
echo -e "  BIDs:    ${BLUE}GET /scrapers/bids?state=$STATE${NC}"
echo -e "  Rejects: ${BLUE}GET /scrapers/rejects?state=$STATE${NC}"
echo ""
