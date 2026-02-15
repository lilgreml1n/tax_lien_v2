#!/bin/bash
##############################################################################
# Quick test - scrape just 10 parcels to verify everything works
##############################################################################

cd "$(dirname "$0")"

echo "🧪 Quick test: scraping 10 parcels..."
./run_scrape_assess.sh Arizona Apache 10 10
