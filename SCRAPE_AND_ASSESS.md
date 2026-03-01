# Scrape & Assess - Separate Scripts

You now have two independent scripts for scraping and assessing. Run them separately:

## 1. Scrape Only

### Scrape all parcels (no limit)
```bash
./scrape.sh Arizona Apache
```

### Scrape limited number of parcels
```bash
./scrape.sh Arizona Apache 200    # Scrape 200 parcels only
./scrape.sh Arizona Coconino 100  # Scrape 100 Coconino parcels
```

### What it does:
- Logs into treasurer and assessor sites
- Extracts parcel IDs and property data
- Saves to database
- **Does NOT assess** - assessment is separate
- Shows progress every minute (page number, elapsed time)
- Continues with human-like delays (2-8s between requests)

### Progress indicators:
- `Initializing...` - Starting up, logging in
- `Scraping page X...` - Processing parcels on that page
- `Page X... (processing with delays)` - Still on same page, processing with delays

---

## 2. Assess Only

### Assess all unassessed parcels
```bash
./assess.sh Arizona Apache
```

### Assess with custom batch size
```bash
./assess.sh Arizona Apache 100     # Process in batches of 100
```

### Assess with budget cap (optional)
```bash
./assess.sh Arizona Apache 50 5000   # Batch 50, only assess parcels <= $5k
./assess.sh Arizona Coconino 50 3000 # Budget cap of $3k per parcel
```

### What it does:
- Checks how many parcels need assessment
- Sends them to DGX Ollama (Capital Guardian AI)
- Processes in batches (~6-10 seconds per parcel)
- Shows progress with batch completion
- Outputs decision (BID, DO_NOT_BID) and reasons

### Results shown:
- Total parcels assessed
- BID count (investment opportunities)
- DO_NOT_BID count (rejected)
- Top rejection reasons
- Sample BID opportunities with details

---

## Typical Workflow

### Small Test (10 parcels)
```bash
./scrape.sh Arizona Apache 10      # ~2 minutes
./assess.sh Arizona Apache         # ~2 minutes (10 parcels × 6-10s each)
```

### Medium Batch (200 parcels)
```bash
./scrape.sh Arizona Apache 200     # ~40 minutes
./assess.sh Arizona Apache 50 5000 # ~35 minutes (200 parcels, max $5k each)
```

### Large Batch (1000+ parcels) - In separate terminal sessions
```bash
# Terminal 1: Scrape (runs ~2-3 hours)
./scrape.sh Arizona Apache 1000

# Terminal 2: Once first 200 are scraped, start assessment
./assess.sh Arizona Apache 50 5000
```

---

## Key Features

✅ **Independent Control** - Start/stop scraping and assessment independently
✅ **Human-like Behavior** - Keeps delays to avoid detection
✅ **Budget Filtering** - Only assess parcels within your investment budget
✅ **Real-time Progress** - Shows page/batch progress every minute
✅ **Lock Prevention** - Prevents accidental concurrent scrapes of same county
✅ **Detailed Results** - Shows BID opportunities and rejection reasons

---

## Troubleshooting

### Scrape stuck on a page?
- Check: `docker logs tax_lien_v2-backend-1 -f | grep Apache`
- Wait 15 minutes before giving up (human delays + network can be slow)
- Or kill with: `kill PID` from lock file message

### Assessment not starting?
- Check for unassessed parcels: `GET /scrapers/unassessed/Arizona/Apache`
- Verify DGX connection: `curl -s http://192.168.100.133:8001/health`
- Check backend logs: `docker logs tax_lien_v2-backend-1`

### Want to see full results?
```bash
# API endpoints:
GET /scrapers/parcels/Arizona/Apache         # All parcels
GET /scrapers/bids?state=Arizona             # BID decisions only
GET /scrapers/rejects?state=Arizona          # Rejections only

# Or use API browser:
http://localhost:8001/docs
```

---

## Architecture

```
┌─────────────────────────────────────────┐
│  scrape.sh (Independent)               │
│  ✓ Treasurer/Assessor lookups          │
│  ✓ Saves raw data to DB                │
│  ✓ No assessment                        │
└─────────────────────────────────────────┘
              ↓ (raw parcels)
         Database (MySQL)
              ↑ (read unassessed)
┌─────────────────────────────────────────┐
│  assess.sh (Independent)               │
│  ✓ Read unassessed parcels             │
│  ✓ Send to DGX Ollama                  │
│  ✓ Store BID/DO_NOT_BID decisions      │
└─────────────────────────────────────────┘
```

Both scripts can run in parallel in different terminals!

---

## Examples

```bash
# Test everything works
./quick_test.sh

# Scrape 50 Coconino parcels
./scrape.sh Arizona Coconino 50

# Assess at $4k budget cap
./assess.sh Arizona Coconino 25 4000

# Scrape ALL Apache (long running - 12+ hours)
./scrape_all_apache.sh

# Monitor scraping in another terminal
watch -n 60 'docker logs tax_lien_v2-backend-1 | grep "Fetching page"'
```
