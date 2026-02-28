# Capital Guardian Assessment Playbook

**Quick reference for understanding parcel scoring.**

---

## TL;DR: Is This Parcel Worth Bidding On?

**Capital Guardian runs 4 gates. Each gate is like a filter:**

| Gate | Type | What It Does | Output |
|------|------|-------------|--------|
| **1** | Python | Reject obvious duds (bankruptcy, shacks, easements) | DO_NOT_BID or PASS |
| **2** | Python | Reject overleveraged (lien too big vs. assessed value) | FAIL or PASS |
| **3** | Python | Flag risky signals (absentee, tight equity, chronic non-payer) | Flags only |
| **4** | AI (Ollama) | Score remaining parcels 0-100 based on market signals | BID or DO_NOT_BID + Risk Score |

**If it reaches Gate 4, it's worth considering. Final decision is yours.**

---

## Gate 1: Kill Switches (Automatic Rejection)

**These are hard stops. If ANY apply, assessment stops, marked DO_NOT_BID immediately.**

### Keyword Rejections
Owner name or legal description contains:
- `BANKRUPTCY` → Owner is bankrupt (can't foreclose)
- `INTERNAL REVENUE` or `FEDERAL TAX LIEN` → IRS lien (super-priority, you won't get paid first)
- `UNITED STATES GOVT` → Government property (complications)

### Structural Rejections
- **Improvement value < $10,000** → Shack/teardown (cost to demolish > value)
- **Lot size < 2,500 sqft** → Too small (can't resell easily)

### Legal Description Rejections
Contains any of:
- `HOA` / `HOMEOWNERS ASSOCIATION` → Can't foreclose against HOA
- `EASEMENT`, `DRAINAGE BASIN`, `PRIVATE ROAD` → Don't own the whole thing
- `LANDLOCKED`, `NO ACCESS` → Can't reach the property
- `UNDIVIDED INTEREST`, `PERCENT INTEREST` → You own a fraction (complications)
- `FLOOD ZONE A` / `FLOOD ZONE AE`, `WETLAND` → Environmental red flag
- `SUPERFUND`, `BROWNFIELD` → Toxic site (liability)

**Decision if Gate 1 triggered:** `DO_NOT_BID` | Risk Score: 0

---

## Gate 2: Liquidity Ratio (Do You Have Enough Equity?)

**Formula:**
```
Ratio = (Billed Amount + $3,000) / (Assessed Value × 0.40)

If Ratio > 1.0 → REJECT (not enough equity)
If Ratio ≤ 1.0 → PASS (you have cushion)
```

**What it means:**
- The `$3,000` = 1 year of carrying costs (taxes, insurance, property maintenance)
- The `× 0.40` = "what could you quickly sell this for?" (40% of assessed = quick-sale value)
- If the ratio is > 1.0, you'd be underwater even after covering costs

**Examples:**

| Billed | Assessed | Ratio | Decision |
|--------|----------|-------|----------|
| $10,000 | $100,000 | 0.325 | ✅ PASS (comfortable equity) |
| $30,000 | $100,000 | 0.825 | ✅ PASS (good equity) |
| $50,000 | $100,000 | 1.325 | ❌ REJECT (overleveraged) |
| $5,000 | $20,000 | 1.0 | ❌ REJECT (break-even, risky) |

**Decision if Gate 2 fails:** `DO_NOT_BID` | Risk Score: 0

---

## Gate 3: Scoring Signals (Flags, Not Rejections)

**These don't reject, they signal risk or opportunity for Gate 4.**

### estate_flag
- **YES:** Owner name contains "ESTATE OF" or "HEIRS OF"
- **Meaning:** Inherited property, often neglected, probate complications, but owner may not care about redemption
- **Market signal:** Slightly higher opportunity (owner less likely to redeem to prevent foreclosure)

### mailing_differs
- **YES:** Mailing address ≠ property address (first 30 chars)
- **Meaning:** Absentee owner (lives elsewhere)
- **Market signal:** Owner may not know property is at tax sale, less likely to redeem

### equity_ratio
- **YES (risky):** (Assessed Value / Billed Amount) < 10x
- **NO (safe):** (Assessed Value / Billed Amount) ≥ 10x
- **Example YES:** $100k assessed, $15k billed = 6.7x (tight, risky if property needs repairs)
- **Example NO:** $100k assessed, $8k billed = 12.5x (comfortable cushion)
- **Meaning:** How much room do you have for unexpected costs?

---

## Gate 4: AI Scoring (Ollama llama3.1:70b)

**Only parcels that passed Gates 1-3 reach here.**

### Scoring Rubric
```
START: 100 points

DEDUCT if:
  -20 pts: Clearly rural (>30 miles from city)
  -15 pts: Vacant land (no improvements)
  -10 pts: Owner is LLC/Corp (harder to foreclose, legal complexity)
  -10 pts: Equity ratio is tight (<10x)
  -15 pts: Chronic delinquent (≥5 years behind on taxes)
  -25 pts: Serial tax sale victim (≥3 prior liens = abandonment pattern)

ADD if:
  +15 pts: Estate owner (inherited = opportunity)
  +10 pts: Absentee owner (less likely to redeem)

RESULT: 0-100 (capped at 100)
```

### What the Score Means
| Score | Signal |
|-------|--------|
| 80-100 | Strong opportunity. Recommend bid. |
| 60-79 | Moderate opportunity. Worth considering. |
| 40-59 | Risky. Only bid if you're comfortable with uncertainty. |
| 20-39 | Very risky. Recommend pass. |
| 0-19 | Do not bid. |

### AI Output
For each parcel that reaches Gate 4, you get:
- `DECISION`: **BID** or **DO_NOT_BID**
- `RISK_SCORE`: Numeric 0-100
- `MAX_BID`: Recommended bid ceiling (billed_amount × 1.1)
- `PROPERTY_TYPE`: single-family / vacant land / mobile home / multi-family / commercial / agricultural
- `OWNERSHIP`: individual / LLC / trust / estate / corporate / unknown
- `CRITICAL_WARNING`: One-sentence risk or opportunity highlight

---

## Real-World Example: Walk Through All 4 Gates

**Parcel: R0001234, Lancaster County, Nebraska**

### Input Data
```
Billed Amount: $22,500
Assessed Total Value: $180,000
Assessed Improvement: $65,000
Assessed Land: $115,000
Owner Name: Estate of Mary Johnson
Mailing Address: 2000 Main St, Denver, CO
Property Address: 1500 Oak Ave, Lincoln, NE
Years Delinquent: 3
Prior Liens Count: 1
Legal Description: Lot 12, Block 4, River View Estates
Lot Size: 0.35 acres
```

### Gate 1 Check
- Owner name = "Estate of Mary Johnson" → contains "ESTATE OF" ✅
- No bankruptcy/IRS keywords ✅
- Improvement = $65,000 > $10,000 ✅
- Lot size = 0.35 acres = 15,246 sqft > 2,500 sqft ✅
- Legal desc = no red flags (no HOA, easements, flood zones) ✅

**Gate 1 Result: PASS** → Continue to Gate 2

### Gate 2 Check
```
Ratio = (22,500 + 3,000) / (180,000 × 0.40)
      = 25,500 / 72,000
      = 0.354
```
**Gate 2 Result: PASS** (0.354 < 1.0, plenty of equity) → Continue to Gate 3

### Gate 3 Check
- estate_flag: **YES** (contains "ESTATE OF")
- mailing_differs: **YES** (Denver CO ≠ Lincoln NE)
- equity_ratio: (180,000 / 22,500) = 8x = **YES** (< 10x, tight equity)

**Gate 3 Result: 3 flags computed** → Send to LLM for Gate 4

### Gate 4 (LLM) Scoring
```
Base: 100 pts
-10 (tight equity <10x)
+15 (estate owner)
+10 (absentee owner)
= 115 capped at 100
= FINAL SCORE: 100
```

**Gate 4 Output:**
```
DECISION: BID
RISK_SCORE: 100
MAX_BID: $24,750 (billed × 1.1)
PROPERTY_TYPE: single-family
OWNERSHIP: estate
CRITICAL_WARNING: Estate property with absentee heir — high redemption uncertainty but opportunity if heirs unaware of sale
```

**Assessment Complete:** This is a strong BID candidate. Owner may not redeem (estate, out-of-state), equity cushion is good, and property condition seems reasonable.

---

## Frequently Asked Questions

**Q: If AI says BID, should I definitely bid?**
A: No. The assessment is a screening tool. You should:
1. Do your own physical inspection
2. Check property taxes, codes violations, mortgage status
3. Understand local redemption rules
4. Verify you can actually sell/rent it afterward

**Q: What if AI says DO_NOT_BID but I think the property is a gem?**
A: You can override. The system is conservative to avoid false positives. But pay attention to the KILL_SWITCH reason—if it's "bankruptcy", that's a hard stop for good reason.

**Q: How long does Gate 4 (AI) take?**
A: ~6-10 seconds per parcel (Ollama llama3.1:70b API call). For 1,200 parcels across 3 counties, expect 2-3 hours total.

**Q: Can I see the raw AI response?**
A: Yes. Each parcel record in the `assessments` table has `ai_full_response` (text field) with the full LLM output.

**Q: What if a field is missing (e.g., no owner name)?**
A:
- Gate 1: Treats missing data as "pass that check" (benefit of doubt)
- Gate 2: If assessed_value is unknown, skips liquidity ratio (marks as SKIPPED)
- Gate 3: If data is null, flags marked NO or UNKNOWN
- Gate 4: LLM gets "N/A" for missing fields and adjusts scoring

---

## Running Assessment

**Command:**
```bash
./assess.sh Nebraska Lancaster    # Full batch, default batch size
./assess.sh Nebraska Sarpy 500    # Batch of 500 (slower)
./assess.sh Nebraska Saline 1000  # Batch of 1000 (faster, harder on DGX)
```

**Check progress:**
```bash
curl -s http://localhost:8001/scrapers/unassessed/Nebraska/Lancaster
# Returns: {"count": 489, "total_parcels": 509}
```

**View results:**
```bash
curl -s http://localhost:8001/scrapers/bids/Nebraska/Lancaster?limit=20
# Returns: Top 20 BID parcels with scores
```

---

## Tips

1. **Estate properties often under-redeem.** If estate_flag=YES and mailing_differs=YES, that's a strong signal.
2. **Tight equity (<10x) is a real risk.** If property needs $30k in repairs and you only have $5k cushion, you lose money.
3. **Prior liens ≥3 = abandonment.** Parcel's been sold at tax sale 3+ times. Why?
4. **Delinquency ≥5 years = chronic non-payer.** Might be a deadbeat. Might be fighting with county. Investigate.
5. **Absentee owners rarely redeem.** But they also rarely maintain property. Inspect before bidding.

---

## Glossary

- **Gate:** Filter/checkpoint in the assessment
- **Kill Switch:** Hard rejection (stops assessment immediately)
- **Billed Amount:** Total amount owed to the county (what you'd pay at auction)
- **Assessed Value:** County's estimate of property value (used for equity calculations)
- **Equity:** Difference between assessed value and lien amount (your potential profit)
- **Liquidity Ratio:** Math formula that tests if there's enough equity cushion
- **Absentee Owner:** Mailing address ≠ property address (owner lives elsewhere)
- **Estate:** Inherited property (owner has passed away)
- **Prior Liens:** Number of times this parcel was sold at tax sale before
- **Redemption:** When the owner pays back taxes + penalties before foreclosure (kills the tax sale)
- **Risk Score:** 0-100 rating of how good the opportunity is

---

**Updated:** 2026-02-28
