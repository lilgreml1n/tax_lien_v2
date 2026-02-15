#!/usr/bin/env python3
"""Quick test to see what GIS data is available from Apache County"""
import httpx
import re

# Test parcel
parcel_id = "R0106010"

# Try Assessor page
assessor_url = f"https://eagleassessor.co.apache.az.us/assessor/taxweb/account.jsp?accountNum={parcel_id}"

print(f"Checking GIS data for {parcel_id}...")
print(f"URL: {assessor_url}\n")

response = httpx.get(assessor_url, verify=False, follow_redirects=True)

# Look for common GIS patterns
patterns = [
    (r"latitude[\"']?\s*[:=]\s*([0-9.-]+)", "Latitude"),
    (r"longitude[\"']?\s*[:=]\s*([0-9.-]+)", "Longitude"),
    (r"lat[\"']?\s*[:=]\s*([0-9.-]+)", "Lat"),
    (r"lng[\"']?\s*[:=]\s*([0-9.-]+)", "Lng"),
    (r"coords?\s*[:=]\s*([0-9.-]+)[,\s]+([0-9.-]+)", "Coordinates"),
    (r"GIS.*?([0-9.-]+)[,\s]+([0-9.-]+)", "GIS"),
    (r"Location.*?([0-9.-]+)[,\s]+([0-9.-]+)", "Location"),
]

print("Searching for GIS data...")
found = False
for pattern, name in patterns:
    matches = re.findall(pattern, response.text, re.IGNORECASE)
    if matches:
        print(f"✓ Found {name}: {matches[:3]}")
        found = True

if not found:
    print("✗ No GIS coordinates found in standard patterns")
    print("\nSearching for 'map' links...")
    map_links = re.findall(r'href="([^"]*(?:map|gis)[^"]*)"', response.text, re.IGNORECASE)
    if map_links:
        print(f"✓ Found map links: {map_links[:3]}")

    print("\nSearching for coordinate-like numbers...")
    coords = re.findall(r'(-?[0-9]{1,3}\.[0-9]{4,})', response.text)
    if coords:
        print(f"✓ Found potential coordinates: {coords[:10]}")

# Check for parcel location / address
print("\nSearching for address/location...")
address_patterns = [
    (r"(?:Situs|Property|Physical)\s+(?:Address|Location)[:\s]+([^<\n]+)", "Property Address"),
    (r"<td[^>]*>\s*Address[^<]*</td>\s*<td[^>]*>([^<]+)", "Address Field"),
]

for pattern, name in address_patterns:
    matches = re.findall(pattern, response.text, re.IGNORECASE)
    if matches:
        print(f"✓ {name}: {matches[0].strip()}")

print("\n" + "="*50)
print("Recommendation:")
print("="*50)
