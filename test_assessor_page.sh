#!/bin/bash
# Check what data is actually on the Apache County assessor page

PARCEL="R0106010"
URL="https://eagleassessor.co.apache.az.us/assessor/taxweb/account.jsp?accountNum=$PARCEL"

echo "Fetching assessor page for $PARCEL..."
echo "URL: $URL"
echo ""

curl -s "$URL" | grep -i -E "(acre|sqft|zone|zoning|value|legal)" | head -30

echo ""
echo "========================================="
echo "Searching for specific patterns:"
echo "========================================="

HTML=$(curl -s "$URL")

echo ""
echo "Acreage:"
echo "$HTML" | grep -i -o ".[0-9.]\+\s*ac" | head -3

echo ""
echo "Values:"
echo "$HTML" | grep -i -o "value[^<]*\$[0-9,]+" | head -5

echo ""
echo "Legal/Zoning:"
echo "$HTML" | grep -i -E "(legal|zone)" | sed 's/<[^>]*>//g' | head -10
