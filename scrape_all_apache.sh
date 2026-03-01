#!/bin/bash
##############################################################################
# Quick script to scrape ALL parcels from Apache County (no limit)
##############################################################################

cd "$(dirname "$0")"

echo "🚀 Scraping ALL parcels from Apache County..."
echo "⚠️  This may take 12-15 hours with human-like delays"
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    ./scrape.sh Arizona Apache 0
else
    echo "Cancelled."
fi
