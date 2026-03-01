#!/bin/bash

# Saline County, NE - Scraper Launch Script (Fixed)
# Built by Gemini using the Scraper Building Guide templates.

API_URL="http://localhost:8001"

echo "----------------------------------------------------"
echo "1. REGISTERING SALINE COUNTY CONFIG..."
echo "----------------------------------------------------"
curl -X POST "$API_URL/scrapers/config" -H "Content-Type: application/json" -d '{"state":"Nebraska","county":"Saline","scraper_name":"app.scrapers.nebraska.saline.SalineScraper"}'

echo -e "\n\n----------------------------------------------------"
echo "2. STARTING SCRAPE (INGESTING EXCEL DATA)..."
echo "----------------------------------------------------"
curl -X POST "$API_URL/scrapers/scrape/Nebraska/Saline"

echo -e "\n\n----------------------------------------------------"
echo "3. VERIFYING PROGRESS (WAITING 5 SECONDS)..."
echo "----------------------------------------------------"
sleep 5
curl -X GET "$API_URL/scrapers/checkpoint/Nebraska/Saline"

echo -e "\n\n----------------------------------------------------"
echo "NEXT STEP: Run the Backfill in iTerm"
echo "command: python3 backend/app/backfill_bids.py --county Nebraska/Saline"
echo "----------------------------------------------------"
