#!/bin/bash
##############################################################################
# View all BID opportunities (parcels Capital Guardian approved)
#
# Usage:
#   ./view_bids.sh                    # All counties
#   ./view_bids.sh Arizona            # Arizona only
#   ./view_bids.sh Arizona Mohave     # Mohave County only
#   ./view_bids.sh Arizona Apache     # Apache County only
##############################################################################

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

STATE="${1:-}"
COUNTY="${2:-}"

# Build query params
PARAMS="limit=100"
if [ -n "$STATE" ]; then
    PARAMS="$PARAMS&state=$STATE"
fi

# County filter applied client-side (API only supports state filter)
COUNTY_LABEL=""
if [ -n "$COUNTY" ]; then
    COUNTY_LABEL=" / $COUNTY"
fi

LABEL="${STATE:-All States}${COUNTY_LABEL}"

echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}Investment Opportunities (BID) — $LABEL${NC}"
echo -e "${BLUE}========================================${NC}\n"

curl -s "http://localhost:8001/scrapers/bids?$PARAMS" | jq -r --arg county "$COUNTY" '
    if length == 0 then
        "No BID parcels found yet. Run scrape + assess first."
    else
        [
            if $county != "" then
                .[] | select(.county == $county)
            else
                .[]
            end
        ] |
        if length == 0 then
            "No BID parcels found for that county yet."
        else
            .[] |
            "Parcel: \(.parcel_id)
  State/County: \(.state) / \(.county)
  Billed: $\(.billed_amount)
  Risk Score: \(.risk_score)/100
  Property Type: \(.property_type)
  Ownership: \(.ownership_type)
  Max Bid: $\(.max_bid)
  Warning: \(.critical_warning)
  ---"
        end
    end
'

echo -e "\n${BLUE}View in browser: http://localhost:8001/docs${NC}\n"
