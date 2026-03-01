# LienHunter v2 — Monetization Roadmap

**Last Updated:** 2026-02-24
**Status:** Planning — not yet started
**Author:** _da5id + Claude

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Business Model & Pricing](#business-model--pricing)
3. [Technical Requirements](#technical-requirements)
4. [Phased Implementation](#phased-implementation)
5. [Financial Analysis](#financial-analysis)
6. [Risks & Mitigations](#risks--mitigations)
7. [Fast-Track: 10 Weeks to First Dollar](#fast-track-10-weeks-to-first-dollar)

---

## Executive Summary

LienHunter v2 has a working core engine: automated county scraping, AI-powered investment assessment (Capital Guardian), and a human review pipeline. Nobody else in the market offers LLM-driven BID/DO_NOT_BID recommendations for tax liens. This is the moat.

**What exists today:**
- 2 working AZ county scrapers (Apache, Mohave) + 1 partial (Coconino)
- Capital Guardian AI: 4-gate assessment with llama3.1:70b on DGX Spark
- React frontend with parcel list, detail view, and review checklist
- FastAPI backend with 50+ endpoints, MySQL database
- Checkpoint/resume, backfill, Discord notifications

**What's missing to charge money:**
- User accounts and authentication
- Subscription billing (Stripe)
- Production deployment (domain, SSL, hosting)
- More counties (at least 4 for launch)
- Frontend polish (routing, auth flow, mobile)

**Bottom line:** 8-10 weeks of focused development to reach first paying customer. Break-even on hosting at 5 subscribers. Solo business viable at 100 subscribers (~$100k ARR).

---

## Business Model & Pricing

### Target Customers

**Primary: Individual Tax Lien Investors**
- Capital: $20k-$200k
- Deploying across 5-50 liens per auction season
- Currently spending 10-40 hours per season manually researching on county websites
- Pain: fragmented county data, no AI analysis, spreadsheet-based tracking

**Secondary: Small Investment Clubs**
- 2-5 people pooling capital
- Need shared visibility into deal pipeline
- Want role-based access (researcher vs decision-maker)

**Tertiary: Institutional Buyers**
- 100+ liens, need API access and portfolio management
- Want custom scraper requests and dedicated support
- Phase 3 target, not Phase 1

### Pricing Tiers

| Tier | Monthly | Annual (20% off) | What They Get |
|------|---------|-------------------|---------------|
| **Scout** | $29/mo | $279/yr | 1 state, 3 counties, 100 AI assessments/mo, parcel search, email alerts |
| **Hunter** | $79/mo | $759/yr | 1 state, all counties, 500 AI assessments/mo, portfolio tracker, Discord + email alerts, priority scrape scheduling |
| **Pro** | $149/mo | $1,429/yr | All available states, unlimited AI assessments, API access (1,000 calls/mo), CSV export, comparable sales, advanced filters |
| **Institutional** | $499/mo | Custom | Multi-user accounts, full API, custom scraper requests, dedicated support, white-label option |

**Pricing rationale:**
- Scout at $29 undercuts FastLien ($49) while offering AI assessment they don't have
- Hunter at $79 is the sweet spot for serious individual investors — 500 assessments covers 2-3 auction seasons
- Pro at $149 is below Tax Sale Resources Pro ($147/mo) with better AI analysis
- The AI assessment is the value. Nobody else has an LLM evaluating parcels through a 4-gate investment framework

### Competitive Landscape

| Competitor | Price | Strengths | Weaknesses vs LienHunter |
|-----------|-------|-----------|--------------------------|
| Tax Sale Resources | $49-$497/mo | Nationwide, AVM comps, established | No AI assessment, no BID/DO_NOT_BID, research-only |
| FastLien | $49/mo | Simple UX, auction calendar, ROI tracking | No AI analysis, no scraping, no assessment pipeline |
| Tax Lien Software | $149 one-time | Desktop app, offline | Legacy product, no cloud, no AI, no scraping |
| Bid4Assets | Free for buyers | Actual auction platform, 3,000+ counties | Marketplace, not analysis tool |
| **LienHunter** | $29-$149/mo | AI BID/DO_NOT_BID, 4-gate assessment, scrape + review pipeline | Limited counties (building), no brand yet |

**The moat:** Capital Guardian AI. A structured 4-gate investment framework running on a 70B parameter LLM. Parcels are auto-rejected for bankruptcy, environmental hazards, code violations, insufficient equity. Survivors get risk-scored with estate/absentee owner detection. Nobody else does this. It's the product.

### Revenue Projections

| Subscribers | Mix (Scout/Hunter/Pro/Inst.) | MRR | ARR |
|------------|------------------------------|-----|-----|
| 10 | 3/5/2/0 | $583 | $7,000 |
| 50 | 15/25/8/2 | $3,802 | $45,600 |
| 100 | 30/45/20/5 | $8,340 | $100,000 |
| 250 | 75/110/50/15 | $19,750 | $237,000 |
| 500 | 150/250/80/20 | $39,570 | $475,000 |

---

## Technical Requirements

### Priority Order

Everything below is ordered by "what do you need to charge money." Auth comes first because nothing else works without it.

---

### A. Authentication & Multi-Tenancy

**Priority:** CRITICAL — foundation for everything else
**Complexity:** Large (2-3 weeks)
**Dependencies:** None

**What to build:**
- User registration (email + password) and login
- JWT token-based authentication with refresh tokens
- Middleware protecting all API endpoints (except /health, /docs, registration)
- `users` table: id, email, password_hash, plan_tier, stripe_customer_id, api_key, monthly_assessment_count, created_at
- Tenant isolation on assessments and reviews (user_id FK)
- Shared scrape data: `scraped_parcels` stays global (public county data), assessments are per-user

**Files to create:**
- `backend/app/auth.py` — JWT creation/validation, password hashing (bcrypt), `get_current_user` dependency
- `backend/app/routers/auth.py` — Register, login, password reset, profile endpoints

**Files to modify:**
- `backend/app/database.py` — Add `users` table, add `user_id` column to `assessments`
- `backend/app/main.py` — Add JWT middleware, include auth router
- `backend/app/routers/scrapers.py` — Add user_id filtering to assessment/review endpoints
- `frontend/src/services/api.ts` — Add auth token interceptor to axios

**Key decision:** Scrape data is global (public records, everyone benefits). Assessments are per-user (each investor has their own budget, risk tolerance, and review workflow). Existing assessments get assigned to a "system" user during migration.

---

### B. Stripe Billing

**Priority:** CRITICAL — no revenue without this
**Complexity:** Medium (1-2 weeks)
**Dependencies:** Auth (A) must be complete

**What to build:**
- Stripe Checkout for subscription signup
- Stripe Customer Portal for self-service plan management
- Webhook handler: subscription.created, updated, cancelled, invoice.payment_failed
- Usage metering: count AI assessment calls per user per month
- Plan enforcement middleware: check assessment quota, check county access by tier
- Grace period: don't cut off access immediately on failed payment

**Files to create:**
- `backend/app/routers/billing.py` — Checkout session, portal session, webhook endpoint
- `backend/app/billing.py` — Stripe SDK wrapper, plan definitions, usage tracking

**Files to modify:**
- `backend/app/database.py` — Add `subscriptions` and `usage_logs` tables
- `backend/app/main.py` — Include billing router
- `frontend/src/services/api.ts` — Add billing/checkout API calls

**Cost:** Stripe takes 2.9% + $0.30 per transaction. On $79/month = $2.59/subscriber/month.

---

### C. Frontend Production-Ready

**Priority:** HIGH — users need to log in, navigate, and not hate the UI
**Complexity:** Large (3-4 weeks)
**Dependencies:** Auth (A) for login flow, Billing (B) for settings page

**Current state:** React 19 + Vite + TypeScript. 4 components (Dashboard, ParcelList, ParcelDetail, ReviewForm). All inline CSS. No router, no UI library, no auth flow.

**What to build:**
- React Router: login, register, dashboard, parcels, portfolio, settings, billing pages
- UI component library: **shadcn/ui + Tailwind CSS** (recommended — copy-paste components, no dependency lock-in, accessible)
- Auth flow: login/register pages, protected routes, token storage
- Responsive layout: the split-panel works on desktop but breaks on mobile
- Loading states, error boundaries, empty states, toast notifications
- Settings page with plan info and billing management

**Files to modify:**
- `frontend/package.json` — Add react-router-dom, tailwindcss, shadcn dependencies
- `frontend/src/App.tsx` — Replace with router-based layout (currently a single-page app)
- All 4 components in `frontend/src/components/` — Replace inline CSS with Tailwind
- `frontend/src/services/api.ts` — Add auth token interceptor, error handling

**Files to create:**
- `frontend/src/pages/` — LoginPage, RegisterPage, SettingsPage, BillingPage, PortfolioPage
- `frontend/src/components/ui/` — shadcn component copies
- `frontend/tailwind.config.js`

**Why shadcn/ui:** The current frontend has zero CSS framework — everything is inline `React.CSSProperties` objects. Moving to Tailwind eliminates all of that. shadcn gives pre-built tables, forms, dialogs, cards that you copy into the project. No npm dependency to break. You own the code.

---

### D. Infrastructure for SaaS

**Priority:** HIGH — can't serve customers from localhost
**Complexity:** Medium (1-2 weeks)
**Dependencies:** None technically, but do alongside Auth

**What to build:**
- Move Docker stack to DGX Spark (Layer 6 from PLAN.md)
- nginx reverse proxy with SSL (Let's Encrypt)
- Domain name + DNS
- Database backups (automated mysqldump, daily)
- Monitoring: UptimeRobot free tier on /health endpoint
- CI/CD: GitHub Actions → Docker build → deploy to DGX via SSH
- Structured logging (replace `print()` statements in scrapers.py)
- Production CORS (currently hardcoded to localhost:3000 and localhost:5173)

**Files to create:**
- `docker-compose.prod.yml` — Production overrides: no volume mounts, no --reload, proper secrets
- `nginx/nginx.conf` — Reverse proxy with SSL termination, static file serving
- `.github/workflows/deploy.yml` — CI/CD pipeline
- `backend/app/logging_config.py` — Structured logging setup

**Files to modify:**
- `docker-compose.yml` — Add nginx service
- `backend/app/main.py` — Update CORS origins for production domain
- `.env` — Restructure for proper secrets management (currently only has Discord webhook)

**Hosting architecture:**
```
Internet → nginx (SSL) → FastAPI (:8001) → MySQL (:3306)
                       → React static files
                       → Ollama on DGX (:11434) for AI assessment
```

**Cost estimate:**
| Item | Monthly |
|------|---------|
| DGX Spark electricity | $75 |
| Domain + SSL | $2 |
| SendGrid (email, 100/day free) | $0-20 |
| UptimeRobot monitoring | $0 |
| **Total (self-hosted on DGX)** | **~$77-97** |

If you move to a VPS instead of self-hosting, add $40/month for a Hetzner AX41 or DigitalOcean droplet, keeping DGX for AI inference only.

---

### E. County Expansion

**Priority:** HIGH for launch — need at least 4 counties to be credible
**Complexity:** Medium per county (1-3 days each following the questionnaire)
**Dependencies:** None — can parallelize with other work

**Launch target:** 4 AZ counties (Apache, Mohave, Coconino, Maricopa)

**Phase 2 target:** All 15 AZ counties

**Strategy:**
1. Complete Coconino (partial scraper exists at `backend/app/scrapers/arizona/coconino.py`)
2. Add Maricopa County (largest AZ county, highest parcel volume, most investor interest)
3. Each county follows the established pattern: `NEW_COUNTY_QUESTIONNAIRE.md` → scraper class → register in SCRAPER_REGISTRY → update `backfill_bids.py` COUNTY_REGISTRY

**Priority order for remaining AZ counties (by investor value):**
1. Maricopa (Phoenix metro — 4M+ parcels, most auction activity)
2. Pima (Tucson — second largest)
3. Pinal (fast-growing Phoenix suburb)
4. Yavapai (Prescott — popular retirement/investment area)
5. Navajo, Cochise, Graham, Greenlee, Gila, La Paz, Santa Cruz, Yuma

**Multi-state expansion (Phase 3):**
- Florida: 67 counties, tax certificate sales (similar to AZ liens)
- Texas: 254 counties, tax deed sales (different legal framework — needs research)
- Illinois: Cook County alone is massive
- Each state needs a state-level base scraper since county website patterns are often similar within a state
- New directories: `backend/app/scrapers/florida/`, `backend/app/scrapers/texas/`

---

### F. Notification System

**Priority:** MEDIUM — nice to have for launch, important for retention
**Complexity:** Small-Medium (1 week)
**Dependencies:** Auth (A) for per-user preferences

**Current state:** Discord webhook works (`backend/app/discord_notify.py`). Sends scrape/backfill/assessment status.

**What to build:**
- Refactor `discord_notify.py` into a general notification dispatcher
- Email notifications via SendGrid (free tier: 100 emails/day)
- Per-user notification preferences table
- Notification types:
  - New BID parcels found (parcel ID, amount, score, assessor link)
  - Scrape completed (county, parcel count)
  - Assessment complete (BID count, top opportunities)
  - Auction date reminders (7 days, 1 day before)
  - Plan usage warnings (approaching assessment limit)

**Files to create:**
- `backend/app/notifications.py` — Unified dispatcher (Discord, email, future SMS)

**Files to modify:**
- `backend/app/discord_notify.py` — Refactor to use the dispatcher
- `backend/app/database.py` — Add `notification_preferences` table

---

### G. Portfolio Management

**Priority:** MEDIUM — differentiator for retention, not needed for launch
**Complexity:** Medium (2 weeks)
**Dependencies:** Auth (A) for per-user portfolios

**What to build:**
- New tables: `bids` (bid history), `watchlist` (parcels to monitor), `owned_liens` (purchased liens)
- Capital tracking: total deployed, reserve remaining (30% rule from PLAN.md)
- ROI calculator: expected return based on interest rate, redemption probability, holding period
- Redemption tracking: when liens redeem, interest earned, foreclosure timeline
- Portfolio dashboard with allocation chart
- Enforce: never recommend BID if it would exceed 70% of user's capital deployed

This maps to Layer 4 in PLAN.md. The columns `projected_annual_cost`, `reserve_required`, `total_holding_cost` were spec'd but never built.

**Files to create:**
- `backend/app/routers/portfolio.py` — Portfolio CRUD endpoints
- `frontend/src/pages/PortfolioPage.tsx`

**Files to modify:**
- `backend/app/database.py` — Add bids, watchlist, owned_liens tables
- `backend/app/main.py` — Include portfolio router

---

### H. Data Enrichment

**Priority:** LOW for launch, HIGH for Phase 2 differentiation
**Complexity:** Medium-Large
**Dependencies:** County expansion (E) for enough data to enrich

**What to build:**
- FEMA flood zone API (free, already in TODO.md)
- EPA Superfund proximity check
- Distance to nearest city center
- Comparable sales (Zillow API or careful scraping — legal complexity)
- Visual AI property analysis using DGX Spark (the "secret sauce" from TODO.md)
  - Analyze Google Street View imagery
  - Automated condition scoring: roof, structure, vegetation, access
  - Uses vision models already on DGX (qwen3-vl:32b, llava:34b)

**Files to modify:**
- `backend/app/routers/scrapers.py` — Add enrichment data to assessment context
- `backend/app/database.py` — Add columns: fema_flood_zone, superfund_distance, nearest_city, distance_to_city

---

### I. API Access for Power Users

**Priority:** LOW — Phase 3 feature
**Complexity:** Small-Medium (1 week)
**Dependencies:** Auth (A), Billing (B) for usage enforcement

**What to build:**
- API key generation per user (stored in users table)
- Rate limiting middleware (per key, per plan tier)
- Public API documentation for external consumers
- Webhook callbacks for new BID parcels (push instead of poll)

**Files to create:**
- `backend/app/rate_limiter.py` — Token bucket or sliding window

**Files to modify:**
- `backend/app/main.py` — Rate limiting middleware
- `backend/app/auth.py` — API key validation alongside JWT

---

## Phased Implementation

### Phase 1: "First Dollar" — MVP SaaS (8-10 weeks)

**Goal:** First paying customer.

| Week | What | Details |
|------|------|---------|
| 1-2 | Authentication | User table, JWT, protected endpoints, user_id on assessments |
| 3 | Stripe Billing | 3 plans, Checkout, webhooks, usage metering |
| 4-5 | Frontend Overhaul | React Router, Tailwind/shadcn, login page, protected routes, mobile-friendly |
| 6 | Infrastructure | Domain, SSL, nginx, deploy to DGX, database backups, production CORS |
| 7 | County Expansion | Complete Coconino, add Maricopa (4 total AZ counties) |
| 8 | Email Notifications | SendGrid integration, new BID alerts, scrape status |
| 9-10 | Polish & Launch | Landing page, beta testing, bug fixes, first users |

**What you can charge for at Phase 1:**
- AI-powered BID/DO_NOT_BID (unique in market)
- 4 Arizona counties scraped and assessed
- Human review pipeline with Google Earth checklist
- Email alerts for new opportunities
- That's enough. The AI is the product.

**Where to find early adopters:**
- BiggerPockets tax lien forums
- Facebook groups: "Tax Lien Investing", "Tax Deed & Lien Investors"
- Reddit: r/realestateinvesting, r/taxliens
- YouTube comments on tax lien investing videos
- NTLA (National Tax Lien Association) community
- Offer first 10 users a free month

---

### Phase 2: "Growth" — Retention & Expansion (Months 3-6)

**Goal:** Retain users, attract new ones, cover 100% of Arizona.

| Month | What | Details |
|-------|------|---------|
| 3 | Portfolio Management | Bid tracking, owned liens, capital allocation, ROI calculator |
| 3-4 | Full Arizona Coverage | Add remaining 11 AZ counties (prioritized by investor value) |
| 4 | Data Enrichment | FEMA flood zones, distance to city, enhanced AI prompt |
| 5 | Advanced Features | Saved filters, CSV export, batch approve/reject, auction calendar |
| 5-6 | Notification System | Per-user preferences, auction reminders, usage warnings |

**Phase 2 marketing:**
- "Every Arizona County" — marketing claim that no competitor matches at this price
- Case studies from Phase 1 users (with permission)
- Content marketing: blog posts on AI-powered real estate investing
- YouTube tutorial series on using LienHunter

---

### Phase 3: "Platform" — Defensible Business (Months 6-12)

**Goal:** Build moats, expand TAM, create switching costs.

| Month | What | Details |
|-------|------|---------|
| 6-7 | Florida Expansion | 67 counties, tax certificate sales (similar to AZ) |
| 7-8 | Public API | API keys, rate limiting, webhooks for BID notifications |
| 8-9 | Visual AI Analysis | Street View image analysis on DGX (qwen3-vl, llava) — property condition scoring |
| 9-10 | Texas Expansion | 254 counties, tax deed sales (different legal framework) |
| 10-11 | Multi-User Accounts | Investment clubs, role-based access, audit trail |
| 11-12 | White-Label | Custom branding for institutional buyers, $499+/mo tier |

**Phase 3 moats:**
- Visual AI is genuinely novel — nobody analyzes Street View for tax lien due diligence
- Multi-state coverage creates switching costs (users build history and portfolio in the platform)
- API access enables integrations that lock in power users
- Community features (county discussion forums) create network effects

---

## Financial Analysis

### Cost Structure

**Self-hosted on DGX Spark:**

| Item | Monthly Cost |
|------|-------------|
| DGX Spark electricity | $75 |
| Domain + SSL (Let's Encrypt) | $2 |
| SendGrid email (free → $20 at scale) | $0-20 |
| Monitoring (UptimeRobot free) | $0 |
| Stripe fees (2.9% + $0.30/tx) | Variable |
| **Total fixed** | **$77-97/month** |

**If using VPS + DGX for AI only:**

| Item | Monthly Cost |
|------|-------------|
| VPS (Hetzner AX41 or DigitalOcean) | $40 |
| DGX Spark electricity | $75 |
| Domain + SSL | $2 |
| SendGrid | $0-20 |
| **Total fixed** | **$117-137/month** |

### Break-Even Analysis

| Milestone | Subscribers Needed | Revenue |
|-----------|-------------------|---------|
| Cover hosting (self-hosted) | 2 Hunter ($79) | $158/mo |
| Cover hosting (VPS model) | 2 Hunter ($79) | $158/mo |
| Cover hosting + tools | 4-5 mixed | ~$300/mo |
| Part-time income ($2k/mo) | 30 mixed | ~$2,100/mo |
| Full-time income ($6k/mo) | 85 mixed | ~$6,200/mo |
| Solo business ($100k ARR) | 100 mixed | ~$8,340/mo |

### Revenue Timeline (Realistic)

| Month | Subscribers | MRR | Cumulative Revenue | Notes |
|-------|-----------|-----|-------------------|-------|
| 1-2 | 0 | $0 | $0 | Building MVP |
| 3 | 3-5 | $200-350 | $275 | Launch, early adopters |
| 4 | 8-12 | $550-850 | $975 | Word of mouth |
| 5 | 15-20 | $1,000-1,400 | $2,175 | Content marketing kicks in |
| 6 | 25-35 | $1,750-2,500 | $4,300 | Full AZ coverage drives signups |
| 9 | 50-70 | $3,500-5,000 | $14,000 | |
| 12 | 80-120 | $5,600-8,500 | $36,000 | Multi-state expansion |

**Subscriber acquisition assumptions:** 2-5 new subs/month from organic, 5-10/month with targeted ads in tax lien communities. AZ auction season (February) is peak acquisition.

### Per-Subscriber Economics

At Hunter tier ($79/mo):
- Stripe fee: $2.59 (3.3%)
- AI compute (DGX, amortized): ~$2.00
- Email notifications: ~$0.50
- Support time: ~$5.00 (estimated)
- **Gross margin: ~$68.91 (87%)**

SaaS gross margins above 80% are excellent. The DGX is already paid for, so AI compute cost is essentially just electricity.

---

## Risks & Mitigations

### Legal Risks

**Scraping county data:**
- County websites are public government data with no paywall or login-gated ToS
- hiQ Labs v. LinkedIn (2022) established that scraping publicly available data is generally legal
- **Mitigation:** HumanBehavior class (2-8s delays, rotating user agents) minimizes detection. Never scrape behind authenticated sessions with ToS agreements.

**Investment advice regulations:**
- BID/DO_NOT_BID recommendations could be construed as investment advice
- **Mitigation:** Clear disclaimers on every screen and API response: "LienHunter provides research and analysis tools, not investment advice. All investment decisions are the user's responsibility." Consider a securities attorney consultation before launch ($1,000-2,000).

**Reselling government data:**
- Public records are not copyrightable (government works doctrine)
- **Mitigation:** Market as an "AI analysis platform" not a "data provider." The raw data is public — you're selling the intelligence layer.

### Technical Risks

**County website changes:**
- Counties redesign without notice. One HTML change breaks a scraper.
- **Mitigation:** Per-parcel try/except with NULL fallback already built. Add monitoring: if scrape returns >50% NULLs on a normally-populated field, alert via Discord and pause. Budget 2-4 hours per county per quarter for maintenance.

**DGX Spark single point of failure:**
- All AI assessment runs through one machine. If it goes down, assessments stop.
- **Mitigation:** Add cloud LLM fallback. Groq offers llama3.1-70b at ~$0.59/million tokens (~$0.01-0.03 per assessment). The assessment prompt works with any Ollama-compatible API. Configure automatic failover in `scrapers.py`.

**MySQL at scale:**
- Current single MySQL instance handles thousands of parcels fine. At 100k+ parcels with concurrent users, may hit limits.
- **Mitigation:** Indexes already defined in `database.py`. Move to managed MySQL (PlanetScale, AWS RDS) when MRR exceeds $2,000/month. Or add read replicas.

**Rate limiting from county sites at SaaS scale:**
- More users = more scrapes = more requests to same county sites.
- **Mitigation:** Never scrape the same county from multiple threads simultaneously (already enforced). Scrape data is shared — one scrape serves all users. Consider residential proxy rotation (Bright Data, $15-50/month) if needed.

### Business Risks

**Small market:**
- Tax lien investing is niche. ~50,000-100,000 active individual investors in the US.
- **Mitigation:** Even 0.1% of the market (50-100 users) makes this viable at $100k+ ARR. Don't need a massive TAM for a solo business.

**Seasonality:**
- AZ auctions in February, FL in May-June. Investors may subscribe for auction season and cancel.
- **Mitigation:** Annual plans with 20% discount. Portfolio management features provide year-round value (tracking owned liens, redemption dates). Marketing angle: "Start researching 3 months before your auction."

**Competition from Tax Sale Resources:**
- TSR is established with nationwide coverage and AVM data. They could build AI features.
- **Mitigation:** First-mover advantage on AI assessment. TSR is a large company that moves slowly. By the time they react, you'll have 6-12 months of data and user feedback. Also, TSR starts at $97/month — you undercut with a better product at $79.

**Solo developer burnout:**
- Building and maintaining scrapers for 15+ counties while building SaaS features is a lot.
- **Mitigation:** Prioritize ruthlessly. Phase 1 needs only 4 counties. Automate scraper monitoring. Use Claude Code and LLMs to accelerate development. Hire a part-time contractor for scraper maintenance when revenue hits $3,000/month.

---

## Fast-Track: 10 Weeks to First Dollar

This is the actionable summary. What to do, in order, nothing else.

### Week 1-2: Authentication
- [ ] Create `backend/app/auth.py` (JWT + bcrypt)
- [ ] Create `backend/app/routers/auth.py` (register, login, profile)
- [ ] Add `users` table to `database.py`
- [ ] Add `user_id` to `assessments` table
- [ ] Protect all endpoints with JWT middleware
- [ ] Migrate existing assessments to a system user

### Week 3: Stripe
- [ ] Create Stripe account, set up 3 products (Scout/Hunter/Pro)
- [ ] Create `backend/app/billing.py` and `backend/app/routers/billing.py`
- [ ] Implement Checkout, Customer Portal, webhooks
- [ ] Add assessment usage counter per user per month
- [ ] Add plan tier enforcement on county access + assessment quota

### Week 4-5: Frontend
- [ ] Install React Router + Tailwind CSS + shadcn/ui
- [ ] Build Login/Register pages
- [ ] Add auth token interceptor to api.ts
- [ ] Protected routes (redirect to login if not authenticated)
- [ ] Replace all inline CSS with Tailwind
- [ ] Add Settings page (plan info, billing portal link)
- [ ] Mobile-responsive layout
- [ ] Loading states and error boundaries

### Week 6: Deploy
- [ ] Buy domain name (lienhunter.com or similar)
- [ ] Set up nginx + Let's Encrypt SSL on DGX
- [ ] Create `docker-compose.prod.yml`
- [ ] Update CORS in `main.py` for production domain
- [ ] Set up automated database backups
- [ ] Set up UptimeRobot monitoring on /health

### Week 7: Counties
- [ ] Complete Coconino scraper (assessor wiring)
- [ ] Build Maricopa County scraper (questionnaire → scraper → register)
- [ ] Run initial scrapes for all 4 counties
- [ ] Run Capital Guardian assessment on all scraped data

### Week 8: Notifications
- [ ] Integrate SendGrid for transactional email
- [ ] Email on: new BID parcels, scrape complete, assessment complete
- [ ] Add notification preferences to user settings

### Week 9-10: Launch
- [ ] Build landing page (can be static HTML, just needs a Stripe checkout link)
- [ ] Write 2-3 blog posts for SEO (tax lien investing + AI, how Capital Guardian works)
- [ ] Beta test with 3-5 friends/contacts who invest in tax liens
- [ ] Post in BiggerPockets forums, tax lien Facebook groups, Reddit
- [ ] Offer first 10 users a free month
- [ ] **Ship it**

### What to explicitly SKIP in Phase 1:
- Portfolio management (users can track in spreadsheets for now)
- API access (no institutional users yet)
- Visual AI analysis (Phase 3)
- More than 4 counties (add the rest in Phase 2)
- Mobile app (responsive web is fine)
- CSV export (Swagger UI can show JSON, good enough)
- Comparable sales data (users check Zillow manually)
- Perfect UI (functional beats beautiful — polish in Phase 2)

---

## Appendix: Key File Reference

| File | Monetization Changes Needed |
|------|---------------------------|
| `backend/app/database.py` | Add users, subscriptions, usage_logs, notification_preferences tables. Add user_id to assessments. |
| `backend/app/main.py` | JWT middleware, production CORS, include auth/billing/portfolio routers |
| `backend/app/routers/scrapers.py` | user_id scoping on assessments/reviews, usage metering on AI calls |
| `backend/app/discord_notify.py` | Refactor into general notification dispatcher |
| `frontend/src/App.tsx` | Rebuild with React Router, auth flow, Tailwind |
| `frontend/src/services/api.ts` | Auth token interceptor, error handling |
| `frontend/src/components/*` | Replace inline CSS with Tailwind, add loading/error states |
| `docker-compose.yml` | Add nginx service, create prod variant |
| `.env` | Add Stripe keys, SendGrid key, JWT secret, production domain |

---

## Relationship to Existing Documents

This roadmap **complements** (does not replace) existing project docs:

| Document | Focus | Overlap |
|----------|-------|---------|
| `PLAN.md` | Technical architecture layers (1-8) | Layers 4-8 are incorporated into Phases 1-3 here |
| `TODO.md` | Feature task list | Technical items referenced here with business context added |
| `ENHANCEMENT_ROADMAP.md` | Long-term feature vision | Phase 3 items pull from this |
| `CLAUDE.md` | Developer instructions for AI assistants | No overlap — this is business strategy |
| `GETTING_STARTED.md` | User guide for running the system | Will need updates for SaaS (login, billing, etc.) |

---

*The AI assessment is the product. Everything else is plumbing to let people pay for it.*
