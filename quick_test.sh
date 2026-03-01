#!/bin/bash
##############################################################################
# Quick test - scrape 10 parcels and assess them separately
##############################################################################

cd "$(dirname "$0")"

echo "🧪 Quick test: scraping 10 parcels from Apache County..."
./scrape.sh Arizona Apache 10

echo ""
echo "✓ Scrape complete. Now assess them:"
echo "  ./assess.sh Arizona Apache 10"
