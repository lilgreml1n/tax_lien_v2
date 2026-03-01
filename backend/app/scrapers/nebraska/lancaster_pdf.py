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

def parse_lancaster_pdf(text_content):
    """
    Parses the 'pdftotext -layout' output of the Lancaster 2026 Tax Sale PDF.
    
    Example line:
    ALANETH ALEX LANE TOWNHOMES ADDITION        B000 L001    16-16-320-001-000       718.66     52,000.00         74.98       999999 **NO SITUS** ST, LINCOLNR2
         6500 SOUTH 56TH LLC                  6000 S 25 ST                              LINCOLN        NE    68512              Total Millage: 1.766448000%
    """
    # Regex to find the main parcel line
    # Groups: 1=Subd, 2=Name, 3=Block, 4=Lot, 5=ParcelID, 6=TaxDue, 7=Taxable, 8=Interest, 9=Address, 10=Class
    parcel_regex = re.compile(
        r'^([A-Z0-9]{2,8})\s+(.{1,40})\s+(B\d{3})\s+(L\d{3})\s+(\d{2}-\d{2}-\d{3}-\d{3}-\d{3})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+(.{1,30})\s+([A-Z0-9]{2})',
        re.MULTILINE
    )

    parcels = []
    lines = text_content.split('\n')
    
    for i, line in enumerate(lines):
        match = parcel_regex.match(line)
        if match:
            # The owner name is usually on the NEXT line, indented
            owner_name = None
            if i + 1 < len(lines):
                next_line = lines[i+1].strip()
                # Simple heuristic: owner line doesn't start with a Subd code and is shorter
                if next_line and not re.match(r'^[A-Z0-9]{4,8}', next_line):
                    # Remove trailing address/state info if possible, or just grab the first part
                    # Example: "6500 SOUTH 56TH LLC                  6000 S 25 ST..."
                    owner_match = re.match(r'^(.{1,30})', next_line)
                    if owner_match:
                        owner_name = owner_match.group(1).strip()

            parcels.append({
                "state": "Nebraska",
                "county": "Lancaster",
                "parcel_id": match.group(5),
                "billed_amount": float(match.group(6).replace(',', '')),
                "assessed_total_value": float(match.group(7).replace(',', '')),
                "full_address": match.group(9).strip(),
                "owner_name": owner_name,
                "legal_class": match.group(10).strip(),
                "source_url": "https://app.lincoln.ne.gov/cnty/treasurer/adlist/adlist.pdf"
            })
            
    return parcels

def ingest_parcels(parcels):
    with engine.begin() as conn:
        for p in parcels:
            try:
                conn.execute(text("""
                    INSERT INTO scraped_parcels (
                        state, county, parcel_id, billed_amount, 
                        assessed_total_value, full_address, owner_name, 
                        legal_class, source_url
                    ) VALUES (
                        :state, :county, :parcel_id, :billed_amount, 
                        :assessed_total_value, :full_address, :owner_name, 
                        :legal_class, :source_url
                    ) ON DUPLICATE KEY UPDATE
                        billed_amount = VALUES(billed_amount),
                        assessed_total_value = VALUES(assessed_total_value),
                        owner_name = COALESCE(VALUES(owner_name), owner_name)
                """), p)
            except Exception as e:
                print(f"Error inserting {p['parcel_id']}: {e}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python lancaster_pdf.py <text_file_path>")
        sys.exit(1)
        
    with open(sys.argv[1], 'r') as f:
        content = f.read()
        
    parcels = parse_lancaster_pdf(content)
    print(f"Parsed {len(parcels)} parcels from Lancaster PDF.")
    
    if parcels:
        ingest_parcels(parcels)
        print(f"Successfully ingested {len(parcels)} parcels into the database.")
