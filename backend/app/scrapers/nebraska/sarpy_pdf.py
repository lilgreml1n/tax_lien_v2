import re
import sys
import os
from sqlalchemy import create_engine, text

# Setup paths for local imports
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, "../../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
os.environ.setdefault('PYTHONPATH', project_root)

# Support both local iTerm (localhost) and Docker (db)
DEFAULT_DB = "mysql+pymysql://lienuser:lienpass@localhost:3306/lienhunter"
DB_URL = os.getenv("DATABASE_URL", DEFAULT_DB).replace("@db/", "@localhost/") if not os.getenv("IS_DOCKER") else os.getenv("DATABASE_URL", "mysql+pymysql://lienuser:lienpass@db/lienhunter")

engine = create_engine(DB_URL)

def parse_sarpy_pdf(text_content):
    """
    Parses the 'pdftotext -layout' output of the Sarpy 2026 Tax Sale PDF.
    
    Example line:
    001060074                WILSON/JEFFREY L & KRISTIN A  905 CODY CIR PAPILLION NE 68046                           LOT 106 OVERLAND HILLS                                                                                     2058.31
    """
    # Regex to find the main parcel line
    # Group 1: Parcel ID (9 digits)
    # Group 2: Name
    # Group 3: Address / Legal (we'll try to split if possible, but legal is more important)
    # Group 4: Amount
    parcel_regex = re.compile(
        r'^(\d{9})\s+(.{1,30})\s+(.{1,80})\s+([\d,]+\.\d{2})',
        re.MULTILINE
    )

    parcels = []
    lines = text_content.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        match = parcel_regex.match(line)
        if match:
            pid = match.group(1)
            owner = match.group(2).strip()
            # The middle section is Address + Legal. We'll store it as full_address for now.
            # Usually the address part ends with the state code or zip.
            addr_legal = match.group(3).strip()
            amount = float(match.group(4).replace(',', ''))

            parcels.append({
                "state": "Nebraska",
                "county": "Sarpy",
                "parcel_id": pid,
                "billed_amount": amount,
                "full_address": addr_legal, # We'll refine this in backfill
                "owner_name": owner,
                "source_url": "https://www.sarpy.gov/DocumentCenter/View/8600/2026-DELINQUENT-TAX-LIST"
            })
            
    return parcels

def ingest_parcels(parcels):
    with engine.begin() as conn:
        for p in parcels:
            try:
                conn.execute(text("""
                    INSERT INTO scraped_parcels (
                        state, county, parcel_id, billed_amount, 
                        full_address, owner_name, source_url
                    ) VALUES (
                        :state, :county, :parcel_id, :billed_amount, 
                        :full_address, :owner_name, :source_url
                    ) ON DUPLICATE KEY UPDATE
                        billed_amount = VALUES(billed_amount),
                        owner_name = COALESCE(VALUES(owner_name), owner_name),
                        full_address = COALESCE(VALUES(full_address), full_address)
                """), p)
            except Exception as e:
                print(f"Error inserting {p['parcel_id']}: {e}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python sarpy_pdf.py <text_file_path>")
        sys.exit(1)
        
    with open(sys.argv[1], 'r') as f:
        content = f.read()
        
    parcels = parse_sarpy_pdf(content)
    print(f"Parsed {len(parcels)} parcels from Sarpy PDF.")
    
    if parcels:
        ingest_parcels(parcels)
        print(f"Successfully ingested {len(parcels)} parcels into the database.")
