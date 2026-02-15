#!/bin/bash
##############################################################################
# Quick script to scrape ALL parcels from Apache County (no limit)
##############################################################################

cd "$(dirname "$0")"

echo "🚀 Scraping ALL parcels from Apache County..."
echo "⚠️  This may take 10-20 minutes and pull 2,000+ parcels"
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    ./run_scrape_assess.sh Arizona Apache 0 100
else
    echo "Cancelled."
fi
