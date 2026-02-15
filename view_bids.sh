#!/bin/bash
##############################################################################
# View all BID opportunities (parcels Capital Guardian approved)
##############################################################################

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}Investment Opportunities (BID)${NC}"
echo -e "${BLUE}========================================${NC}\n"

curl -s "http://localhost:8001/scrapers/bids?limit=100" | jq -r '
    if length == 0 then
        "No BID parcels found yet. Run ./run_scrape_assess.sh first."
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
'

echo -e "\n${BLUE}View in browser: http://localhost:8001/docs${NC}\n"
