import asyncio
import os
import re
import json
from playwright.async_api import async_playwright

async def scout_nebraska(page):
    """Find Nebraska statewide and county lists."""
    results = []
    
    # Try a few variants for the PAD list
    urls = [
        "https://revenue.nebraska.gov/PAD/delinquent-real-property-list",
        "https://revenue.nebraska.gov/PAD/nebraska-delinquent-real-property-list"
    ]
    
    for url in urls:
        print(f"[Scout] Visiting {url}...")
        try:
            await page.goto(url, timeout=30000, wait_until="networkidle")
            if "404" not in await page.title():
                excel_links = await page.query_selector_all("a")
                for ex_link in excel_links:
                    ex_href = await ex_link.get_attribute("href")
                    ex_text = await ex_link.inner_text()
                    if ex_href and (".xlsx" in ex_href.lower() or ".xls" in ex_href.lower() or "excel" in ex_text.lower()):
                        if ex_href.startswith("/"):
                            ex_href = "https://revenue.nebraska.gov" + ex_href
                        results.append({"county": "Statewide", "state": "NE", "format": "XLSX", "url": ex_href})
                        print(f"[Scout] Found Statewide Excel: {ex_href}")
                        return results
        except:
            continue

    # Platform Discovery
    platforms = [
        {"name": "ArizonaTaxSale", "url": "https://arizonataxsale.com"},
        {"name": "RealAuction", "url": "https://www.realauction.com"},
        {"name": "Bid4Assets", "url": "https://www.bid4assets.com"}
    ]
    
    for p in platforms:
        try:
            print(f"[Scout] Checking Platform: {p['name']}...")
            await page.goto(p['url'], timeout=30000, wait_until="networkidle")
            # Look for "Upcoming Sales" or "County Lists"
            results.append({"county": "Platform", "state": "N/A", "format": "HTML", "url": p['url']})
        except:
            continue
            
    # Search for specific county pages
    counties = ["Adams", "Buffalo", "Hall", "Furnas", "Franklin", "Saline", "Sarpy", "Lancaster"]
    for county in counties:
        try:
            print(f"[Scout] Searching for {county} County tax list...")
            search_url = f"https://www.google.com/search?q={county}+County+Nebraska+delinquent+tax+list+2026"
            await page.goto(search_url, timeout=30000, wait_until="networkidle")
            
            # Use a more specific selector for search results
            links = await page.query_selector_all("a")
            for link in links:
                href = await link.get_attribute("href")
                if href and ("pdf" in href.lower() or "xlsx" in href.lower() or "xls" in href.lower()) and "tax" in href.lower():
                    fmt = "PDF" if "pdf" in href.lower() else "XLSX"
                    results.append({"county": county, "state": "NE", "format": fmt, "url": href})
                    print(f"[Scout] Found {county} {fmt}: {href}")
                    break
            await asyncio.sleep(2)
        except:
            continue
    
    return results

async def update_markdown(results):
    """Update SCRAPER_RESULTS.md with new findings."""
    md_path = "SCRAPER_RESULTS.md"
    content = "# Automated County Discovery Results\n\n"
    content += "| County | State | Format | URL |\n"
    content += "| --- | --- | --- | --- |\n"
    
    for r in results:
        content += f"| {r['county']} | {r['state']} | {r['format']} | [{r['url']}]({r['url']}) |\n"
    
    content += f"\nLast Updated: {asyncio.get_event_loop().time()}\n"
    
    with open(md_path, "w") as f:
        f.write(content)
    print(f"[Scout] Updated {md_path}")

async def main():
    async with async_playwright() as p:
        # Using a standard user agent to avoid simple bot detection
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        results = []
        try:
            ne_results = await scout_nebraska(page)
            results.extend(ne_results)
        except Exception as e:
            print(f"[Error] {e}")
            
        await update_markdown(results)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
