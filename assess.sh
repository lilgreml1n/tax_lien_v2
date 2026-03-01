#!/bin/bash

##############################################################################
# LienHunter v2 - Assess Only
#
# Usage:
#   ./assess.sh <state> <county> [batch_size] [max_cost] [resume]
#
# Examples:
#   ./assess.sh Arizona Apache              # Assess all unassessed, batch 50
#   ./assess.sh Arizona Apache 100          # Assess all, batch 100
#   ./assess.sh Arizona Apache 50 5000      # Assess all, max $5k per parcel
#   ./assess.sh Arizona Apache 50 5000 resume  # Resume from crash (resets stuck parcels)
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
BATCH_SIZE="${3:-50}"
MAX_COST="${4:-}"
RESUME="${5:-}"

# Validate inputs
if [ -z "$STATE" ] || [ -z "$COUNTY" ]; then
    echo -e "${RED}Usage: ./assess.sh <state> <county> [batch_size] [max_cost]${NC}"
    echo -e "Example: ./assess.sh Arizona Apache 50 5000"
    exit 1
fi

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}LienHunter v2 - Assess Only${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "State:          ${GREEN}$STATE${NC}"
echo -e "County:         ${GREEN}$COUNTY${NC}"
echo -e "Batch Size:     ${GREEN}$BATCH_SIZE${NC}"
if [ -n "$MAX_COST" ]; then
    echo -e "Max Cost/Parcel: ${GREEN}\$$MAX_COST${NC}"
fi
echo -e "${BLUE}========================================${NC}"
echo -e "${YELLOW}⏱️  Assessment uses DGX Ollama (llama3.1:70b)${NC}"
echo -e "   ~6-10 seconds per parcel${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Step 1: Check API health
echo -e "${YELLOW}[1/4] Checking API health...${NC}"
HEALTH=$(curl -s "$API_URL/health" | jq -r '.status' 2>/dev/null || echo "error")
if [ "$HEALTH" = "ok" ]; then
    echo -e "${GREEN}✓ API is healthy${NC}\n"
else
    echo -e "${RED}✗ API is not responding. Is the backend running?${NC}"
    echo -e "${YELLOW}Run: docker-compose up -d${NC}"
    exit 1
fi

# Step 2: Check how many parcels need assessment
echo -e "${YELLOW}[2/4] Checking for unassessed parcels...${NC}"
CHECKPOINT=$(curl -s "$API_URL/scrapers/unassessed/$STATE/$COUNTY" 2>/dev/null || echo "{}")
UNASSESSED=$(echo "$CHECKPOINT" | jq -r '.unassessed_count // 0')

echo -e "${GREEN}✓ Found $UNASSESSED parcels needing assessment${NC}\n"

if [ "$UNASSESSED" = "0" ]; then
    echo -e "${YELLOW}No parcels to assess. All done!${NC}\n"
    exit 0
fi

# Step 3: Trigger assessment
if [ "$RESUME" = "resume" ]; then
    echo -e "${YELLOW}[3/4] Resuming AI assessment (resetting stuck parcels)...${NC}"
else
    echo -e "${YELLOW}[3/4] Starting AI assessment via DGX Ollama...${NC}"
fi

# Build the assessment URL with optional max_cost and resume parameters
ASSESS_URL="$API_URL/scrapers/assess/$STATE/$COUNTY?batch_size=$BATCH_SIZE"
if [ -n "$MAX_COST" ]; then
    ASSESS_URL="$ASSESS_URL&max_cost=$MAX_COST"
fi
if [ "$RESUME" = "resume" ]; then
    ASSESS_URL="$ASSESS_URL&resume=true"
fi

ASSESS_RESPONSE=$(curl -s -X POST "$ASSESS_URL")
ASSESS_JOB=$(echo "$ASSESS_RESPONSE" | jq -r '.job_id // "error"')

if [ "$ASSESS_JOB" = "error" ] || [ -z "$ASSESS_JOB" ]; then
    echo -e "${RED}✗ Failed to start assessment job${NC}"
    echo "Response: $ASSESS_RESPONSE"
    exit 1
fi

echo -e "${GREEN}✓ Assessment job started: $ASSESS_JOB${NC}"
echo -e "${BLUE}Waiting for assessment to complete...${NC}"
echo -e "${YELLOW}  (This takes ~6-10 seconds per parcel)${NC}\n"

# Step 4: Wait for assessment to finish
WAIT_TIME=0
LAST_COUNT=0
NO_PROGRESS_COUNT=0
MAX_NO_PROGRESS=10  # 10 minutes with no progress = timeout

while true; do
    sleep 60  # Check every minute
    WAIT_TIME=$((WAIT_TIME + 60))

    # Check backend logs for completion
    LOGS=$(docker logs tax_lien_v2-backend-1 2>&1 | tail -100)

    if echo "$LOGS" | grep -q "\[$ASSESS_JOB\] DONE"; then
        # Extract count from completion message
        ASSESSED_COUNT=$(echo "$LOGS" | grep "\[$ASSESS_JOB\] DONE" | tail -1 | grep -oE "[0-9]+ parcels" | grep -oE "[0-9]+")
        echo -e "\n${GREEN}✓ Assessment completed!${NC}"
        echo -e "${GREEN}✓ Total assessed: $ASSESSED_COUNT${NC}\n"
        break
    fi

    # Try to extract assessment progress [N/batch_size]
    CURRENT_COUNT=$(echo "$LOGS" | grep -oE "\[[0-9]+/$BATCH_SIZE\]" | tail -1 | sed 's/\[//;s/\/.*//')

    if [ -z "$CURRENT_COUNT" ]; then
        CURRENT_COUNT=0
    fi

    if [ "$CURRENT_COUNT" -gt "$LAST_COUNT" ]; then
        # Making progress!
        LAST_COUNT=$CURRENT_COUNT
        NO_PROGRESS_COUNT=0
        echo -ne "${BLUE}  Assessed $CURRENT_COUNT/$BATCH_SIZE... ${WAIT_TIME}s elapsed (~$((WAIT_TIME / 60)) min)\r${NC}"
    else
        # No progress detected
        NO_PROGRESS_COUNT=$((NO_PROGRESS_COUNT + 1))
        echo -ne "${YELLOW}  Assessing... ${WAIT_TIME}s elapsed (no progress: $NO_PROGRESS_COUNT/$MAX_NO_PROGRESS)\r${NC}"

        if [ $NO_PROGRESS_COUNT -ge $MAX_NO_PROGRESS ]; then
            echo -e "\n${RED}✗ Assessment appears stuck. Check logs:${NC}"
            echo -e "${YELLOW}  docker logs tax_lien_v2-backend-1 -f | grep '\[$ASSESS_JOB\]'${NC}"
            exit 1
        fi
    fi
done

# Step 5: Show results
echo -e "${YELLOW}[4/4] Fetching assessment results...${NC}"
RESULTS=$(curl -s "$API_URL/scrapers/parcels/$STATE/$COUNTY?limit=100")

TOTAL=$(echo "$RESULTS" | jq 'length')
BIDS=$(echo "$RESULTS" | jq '[.[] | select(.decision == "BID")] | length')
REJECTS=$(echo "$RESULTS" | jq '[.[] | select(.decision == "DO_NOT_BID")] | length')
PENDING=$(echo "$RESULTS" | jq '[.[] | select(.decision == null)] | length')

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}ASSESSMENT RESULTS - $STATE / $COUNTY${NC}"
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
        "  \(.parcel_id): $\(.billed_amount) | Risk: \(.risk_score) | Type: \(.property_type)"
    ' | head -10
    echo ""
fi

# Show top rejection reasons
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
echo -e "${GREEN}✓ Assessment pipeline complete!${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "\nView full results:"
echo -e "  Browser API Docs: ${BLUE}http://192.168.100.133:8001/docs${NC}"
echo -e "  All parcels:      ${BLUE}GET /scrapers/parcels/$STATE/$COUNTY${NC}"
echo -e "  BIDs only:        ${BLUE}GET /scrapers/bids?state=$STATE${NC}"
echo -e "  Rejects only:     ${BLUE}GET /scrapers/rejects?state=$STATE${NC}"
echo ""
