# New County Scraper Questionnaire

This is the mandatory intake process before writing a single line of scraper code.
Claude walks through this with you section by section.
You answer the questions, Claude builds the scraper.

**Rule: Do not start coding until ALL sections are answered.**
Getting this wrong means the scraper fails on page 2 or silently misses data.

---

## SECTION 1: Identity

Q1.1  What is the county name?
Q1.2  What state is it in?
Q1.3  What is the auction site URL?
      (If you don't have it yet, search: "{county} county tax lien sale")
      Example: https://apache.arizonataxsale.com/index.cfm?folder=previewitems

---

## SECTION 2: The Entry & Handshake
*These questions determine how we open the door to the site.*

Q2.1  Before you see any data, is there a wall to get through?
      - "Terms & Conditions" / "I Agree" button?
      - A login page? (guest login available, or need credentials?)
      - A CAPTCHA or "I am not a robot" check?
      Note: If yes to any - we need to handle this FIRST or the whole scraper fails.

Q2.2  After you pass the entry wall, what does the URL look like?
      - Does it stay the same when you search? (e.g., always county.gov/search)
        → This means the site uses AJAX or POST requests (harder to scrape)
      - Does the URL change with each parcel? (e.g., county.gov/parcel/R0012345)
        → This means direct URL access is possible (easier to scrape)
      Paste the URL before AND after searching for a parcel.

Q2.3  Does the site require JavaScript to show the data?
      Test: right-click → View Page Source. Can you see the parcel data in the HTML?
      - Yes, data is in the source → straightforward scraping
      - No, source shows blank divs → JavaScript renders it → need Playwright

---

## SECTION 3: Auction / Listing Page
*This is where we get the parcel IDs and bid amounts.*

Q3.1  What does a parcel ID look like on the auction page?
      Example Apache:   R0012345   (letter + 7 digits)
      Example Coconino: 10523456   (8 digits only)

Q3.2  Is there a dollar amount next to each parcel?
      What is the column called exactly? (Face Amount / Billed / Amount Due / other)
      If no amount shown here → we need the Treasurer site (Section 6).

Q3.3  Pagination - how do you get to page 2?
      - Click a page number? (paste the page 2 URL)
      - Click a "Next >" arrow? (paste the page 2 URL)
      - Infinite scroll? (page keeps loading as you scroll down)
      - A "Load More" button?
      Note: If the URL doesn't change on page 2, it's a POST/AJAX request.

Q3.4  How many parcels per page, and roughly how many total?
      Note: "Total available" is tracked in the checkpoint as `total_parcels_available`.
      - PDF/Excel scrapers: set it BEFORE pagination (total is known upfront from the file).
      - HTML paginated scrapers: set it AFTER the loop finishes (best estimate = total scraped).
      → Always set `self.total_parcels_available = N` in the scraper's `scrape()` method.

---

## SECTION 4: Data Structure - One Page or Tabs?
*This is the most commonly missed question. Gets the scraper architecture wrong.*

Q4.1  When you click into a single parcel, is all the data on ONE page,
      or is it split across TABS?
      Common tab patterns:
      - "Summary" tab + "Tax" tab + "Land" tab
      - "Property" tab + "Owner" tab + "Values" tab
      If tabs exist: list the tab names and what data is in each one.
      Note: Each tab = a separate HTTP request = more complexity.

Q4.2  Is there a "Legal Description" field visible?
      Where is it? (main page / which tab / need to expand a section)
      This is critical - the AI scans it for "Estate of", "Easement", "Bankruptcy".

Q4.3  Is any of the data inside a PDF?
      Examples: "View Tax Bill" → opens PDF, or "Download Notice" → PDF
      If yes: which fields are in the PDF vs on the HTML page?
      Note: PDF data requires a separate PDF-to-text parsing step.

---

## SECTION 5: The Fields We Need
*Confirm what's available and what it's called on THIS specific site.*

Q5.1  Owner information - what do you see?
      - Owner Name field label: (e.g., "Owner", "Taxpayer", "Deed Holder")
      - Mailing Address field label: (e.g., "Mailing Address", "Tax Address")
      - Is the mailing address on the same page as the property address?
      Note: Mailing ≠ property address = absentee owner = high priority target.

Q5.2  Property value fields - what are they called EXACTLY on this site?
      We need to know the exact label to scrape it reliably.
      - Total assessed value: (e.g., "Total Value", "Full Cash Value", "AV Total")
      - Land value only: (e.g., "Land Value", "Site Value", "AV Land")
      - Improvement/building value: (e.g., "Improvement Value", "Building Value",
        "Non-Land Value", "AV Improvements")
      Note: Improvement value must be > $10k or it's likely a shack/empty lot.

Q5.3  Land use / property type - what codes does this site use?
      Look at 3-4 parcels. What is the "Use Code" or "Property Type" field called?
      What code means "Single Family Residential"? (e.g., 0100, SFR, R1, 1001)
      What code means "Vacant Land"? (e.g., 0900, VAC, 9000)
      Note: We only want residential improved properties, not raw land.

Q5.4  Is there a "Last Sale Date" or "Date of Last Transfer" field?
      Where is it? Last sale > 30 years ago = likely inherited/unmanaged estate.

Q5.5  Is there a "Year Built" or structure age field?
      Where is it? Old structure + low improvement value = likely a shack.

---

## SECTION 6: Treasurer / Billed Amount
*Where does the actual lien amount (what you pay) come from?*

Q6.1  Is the billed/lien amount already on the auction page? (yes / no)
      If yes → skip this section.

Q6.2  If no: is there a separate Treasurer website?
      (Search: "{county} county treasurer parcel account lookup")
      Example: https://eagletreasurer.co.apache.az.us:8443/treasurer/treasurerweb

Q6.3  What is the "total owed" field called on the treasurer site?
      (e.g., "Total Billed", "Amount Due", "Delinquent Amount")

Q6.4  Does the treasurer require login? (guest / credentials / none)

---

## SECTION 7: Building / Code Enforcement
*The stealth filter - catches demolition orders and unsafe structures.*

Q7.1  Does this county have a Building Department / Code Enforcement website?
      (Search: "{county} county building department permit lookup")

Q7.2  Can you search by parcel ID or address for permit history?

Q7.3  Look up one parcel. Do you see any of these fields:
      - "Open Violations" or "Code Violations"
      - "Demolition Order" or "Demolition Permit"
      - "Unsafe Structure Notice" or "Red Tag"
      - "Stop Work Order"
      If yes: what are they called and where on the page?

Q7.4  Is this data available without login?

---

## SECTION 8: Anti-Bot Check
*Determine how aggressive the site's bot detection is.*

Q8.1  Click through 5 different parcels manually, one after another.
      Does the site:
      - Slow down noticeably?
      - Show a CAPTCHA?
      - Block you or show an error?
      - Show nothing different? (good)

Q8.2  Does the site use Cloudflare or similar protection?
      (Look for "Checking your browser..." or Cloudflare branding)

Q8.3  Does any page require cookies set by a previous page to work?
      (i.e., you must visit the homepage before the parcel page loads)

---

## SECTION 9: Live Verification
*Confirm the data flows with real parcel IDs before writing code.*

Q9.1  Give me 3 sample parcel IDs from the auction page.

Q9.2  For one of those parcel IDs, open the assessor page manually.
      Report back exactly what you see for:
      - Owner Name:
      - Owner Mailing Address:
      - Property Address (same or different from mailing?):
      - Total Assessed Value:
      - Improvement / Building Value:
      - Land Use Code:
      - Legal Description (first 50 chars):
      - Year Built:
      - Last Sale Date:
      - Any tabs or PDFs to navigate?

Q9.3  For the same parcel, open the treasurer page (if separate).
      - Total Billed / Amount Due:
      - Direct URL that works: (paste it)

Q9.4  Anything unexpected or weird?
      Examples: data in iframe, redirects, session expiry, odd ID format

---

## SECTION 10: Priorities

Q10.1  How important is owner data for this county?
       (Critical / Nice to have / Skip for now)

Q10.2  Is building/code enforcement data available?
       (Yes - add it / Not found / Skip for now)

Q10.3  How many parcels total do you expect?

Q10.4  Any hard deadline?

---

## WHAT HAPPENS AFTER YOU ANSWER

Once all sections are complete, Claude will:

1. Confirm the exact data contract (which fields will be populated vs NULL)
2. Identify any special handling needed (Playwright, PDF parsing, tab navigation)
3. Write the scraper: `backend/app/scrapers/{state}/{county}.py`
   - Must set `self.total_parcels_available` in `scrape()` (before limit is applied)
4. Register the scraper via the API
5. Run a 10-parcel test and show you the output
6. Fix any issues before running the full scrape

---

## HOW TO USE THIS

Say: **"Let's add {County} County"**
Claude will ask these questions one section at a time and wait for your answers.
