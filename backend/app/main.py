from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse, FileResponse
from app.database import create_tables
from app.routers.calendar import router as calendar_router
from app.routers.scrapers import router as scrapers_router
from app.routers.review import router as review_router
from app.scheduler import start_scheduler
from app.seed_calendar import seed_known_events
import os

app = FastAPI(
    title="LienHunter v2",
    description="Tax Lien Investment Platform - Scrape, Assess, Review, Buy",
    version="2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(calendar_router)
app.include_router(scrapers_router)
app.include_router(review_router)


@app.on_event("startup")
def startup():
    create_tables()
    seed_known_events()
    start_scheduler()


# ==================== Docs file serving ====================

DOCS_DIR = "/app/docs"

@app.get("/docs-static/due_diligence_checklist.pdf", tags=["Documentation"], include_in_schema=False)
def serve_due_diligence():
    path = os.path.join(DOCS_DIR, "due_diligence_checklist.pdf")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, media_type="application/pdf", filename="due_diligence_checklist.pdf")

@app.get("/docs-static/auction_day_bid_plan.pdf", tags=["Documentation"], include_in_schema=False)
def serve_auction_plan():
    path = os.path.join(DOCS_DIR, "auction_day_bid_plan.pdf")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, media_type="application/pdf", filename="auction_day_bid_plan.pdf")

@app.get("/docs-static/state_calendar.png", tags=["Documentation"], include_in_schema=False)
def serve_state_calendar():
    path = os.path.join(DOCS_DIR, "state_calendar.png")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, media_type="image/png")


@app.get("/health")
def health():
    return {"status": "ok", "version": "2.0"}


@app.get("/playbook", response_class=HTMLResponse, tags=["Documentation"])
def get_playbook():
    """Investment playbook — due diligence checklist, auction day plan, and state calendar."""
    html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>LienHunter — Investor Playbook</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: 'Georgia', serif;
      background: #0f1117;
      color: #e8e0d0;
      min-height: 100vh;
    }

    header {
      background: linear-gradient(135deg, #1a1f2e 0%, #0f1117 100%);
      border-bottom: 1px solid #2a3040;
      padding: 40px 48px 32px;
    }

    .header-inner {
      max-width: 960px;
      margin: 0 auto;
    }

    .eyebrow {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 3px;
      text-transform: uppercase;
      color: #c8a84b;
      margin-bottom: 12px;
    }

    h1 {
      font-size: 38px;
      font-weight: normal;
      color: #f0e8d8;
      letter-spacing: -0.5px;
      line-height: 1.2;
    }

    h1 span {
      color: #c8a84b;
    }

    .subtitle {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      font-size: 15px;
      color: #8090a8;
      margin-top: 10px;
      line-height: 1.5;
    }

    nav {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      display: flex;
      gap: 24px;
      margin-top: 24px;
    }

    nav a {
      font-size: 13px;
      color: #8090a8;
      text-decoration: none;
      border-bottom: 1px solid transparent;
      padding-bottom: 2px;
      transition: color 0.2s, border-color 0.2s;
    }

    nav a:hover {
      color: #c8a84b;
      border-bottom-color: #c8a84b;
    }

    main {
      max-width: 960px;
      margin: 0 auto;
      padding: 48px 48px 80px;
    }

    .section-title {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 3px;
      text-transform: uppercase;
      color: #c8a84b;
      margin-bottom: 20px;
    }

    /* Document cards */
    .cards {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 20px;
      margin-bottom: 56px;
    }

    .card {
      background: #161b27;
      border: 1px solid #2a3040;
      border-radius: 8px;
      padding: 28px 28px 24px;
      display: flex;
      flex-direction: column;
      gap: 12px;
      transition: border-color 0.2s, transform 0.15s;
      text-decoration: none;
      color: inherit;
    }

    .card:hover {
      border-color: #c8a84b;
      transform: translateY(-2px);
    }

    .card-icon {
      font-size: 28px;
      line-height: 1;
    }

    .card-title {
      font-size: 18px;
      color: #f0e8d8;
      font-weight: normal;
      line-height: 1.3;
    }

    .card-desc {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      font-size: 13px;
      color: #8090a8;
      line-height: 1.6;
      flex: 1;
    }

    .card-action {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 13px;
      font-weight: 600;
      color: #c8a84b;
      margin-top: 4px;
    }

    .card-action::after {
      content: '→';
    }

    /* Calendar section */
    .calendar-section {
      border-top: 1px solid #2a3040;
      padding-top: 40px;
    }

    .calendar-wrapper {
      margin-top: 20px;
      border: 1px solid #2a3040;
      border-radius: 8px;
      overflow: hidden;
      background: #161b27;
    }

    .calendar-wrapper img {
      width: 100%;
      display: block;
    }

    .calendar-caption {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      font-size: 12px;
      color: #4a5568;
      padding: 12px 16px;
      border-top: 1px solid #2a3040;
      text-align: center;
    }

    footer {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      text-align: center;
      padding: 24px;
      font-size: 12px;
      color: #3a4455;
      border-top: 1px solid #1e2535;
    }
  </style>
</head>
<body>

<header>
  <div class="header-inner">
    <div class="eyebrow">LienHunter v2</div>
    <h1>Investor <span>Playbook</span></h1>
    <p class="subtitle">Field guides, checklists, and reference materials for tax lien investing.</p>
    <nav>
      <a href="/playbook">Playbook</a>
      <a href="/docs">API Reference</a>
      <a href="/getting-started">Getting Started</a>
      <a href="/instructions">Quick Start</a>
    </nav>
  </div>
</header>

<main>

  <div class="section-title">Field Documents</div>

  <div class="cards">
    <a class="card" href="/docs-static/due_diligence_checklist.pdf" target="_blank">
      <div class="card-icon">📋</div>
      <div class="card-title">Due Diligence Checklist</div>
      <div class="card-desc">
        Step-by-step property research workflow. Google Earth, GIS portal confirmation,
        tax record review, mailing vs. physical address check, and estimated value lookup
        via Zillow, Redfin, or Propstream.
      </div>
      <div class="card-action">Open PDF</div>
    </a>

    <a class="card" href="/docs-static/auction_day_bid_plan.pdf" target="_blank">
      <div class="card-icon">🏛️</div>
      <div class="card-title">Auction Day Bid Plan</div>
      <div class="card-desc">
        Your game plan for auction day. Max bid limits, bidding strategy,
        prioritized parcel list, and decision rules so you stay disciplined
        when the room gets competitive.
      </div>
      <div class="card-action">Open PDF</div>
    </a>
  </div>

  <div class="calendar-section">
    <div class="section-title">State-by-State Auction Calendar</div>
    <div class="calendar-wrapper">
      <img src="/docs-static/state_calendar.png" alt="State-by-State Tax Defaulted Property Calendar" />
      <div class="calendar-caption">
        Prime Lien and Deed Sale Opportunities — Low / Medium / High activity by month
      </div>
    </div>
  </div>

</main>

<footer>
  LienHunter v2 &nbsp;·&nbsp; Internal use only
</footer>

</body>
</html>"""
    return HTMLResponse(content=html)


@app.get("/instructions", response_class=HTMLResponse, tags=["Documentation"])
def get_instructions():
    """View the LienHunter v2 quick start guide and API instructions."""
    instructions_path = "/INSTRUCTIONS.md"

    if not os.path.exists(instructions_path):
        return HTMLResponse(content="<h1>Instructions not found</h1><p>INSTRUCTIONS.md is missing from the project root.</p>", status_code=404)

    with open(instructions_path, "r") as f:
        markdown_content = f.read()

    # Escape backticks for JavaScript
    escaped_markdown = markdown_content.replace('`', '\\`')

    # Convert markdown to HTML (basic conversion)
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>LienHunter v2 - Instructions</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                max-width: 900px;
                margin: 40px auto;
                padding: 0 20px;
                line-height: 1.6;
                color: #333;
            }}
            h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
            h2 {{ color: #34495e; margin-top: 30px; border-bottom: 2px solid #ecf0f1; padding-bottom: 8px; }}
            h3 {{ color: #7f8c8d; margin-top: 20px; }}
            code {{
                background: #f4f4f4;
                padding: 2px 6px;
                border-radius: 3px;
                font-family: 'Monaco', 'Courier New', monospace;
                font-size: 0.9em;
            }}
            pre {{
                background: #2c3e50;
                color: #ecf0f1;
                padding: 15px;
                border-radius: 5px;
                overflow-x: auto;
            }}
            pre code {{
                background: transparent;
                color: #ecf0f1;
                padding: 0;
            }}
            ul {{ margin-left: 20px; }}
            li {{ margin: 8px 0; }}
            .badge {{
                background: #3498db;
                color: white;
                padding: 3px 8px;
                border-radius: 3px;
                font-size: 0.85em;
                font-weight: bold;
            }}
            .warning {{
                background: #fff3cd;
                border-left: 4px solid #ffc107;
                padding: 12px;
                margin: 15px 0;
            }}
            .success {{
                background: #d4edda;
                border-left: 4px solid #28a745;
                padding: 12px;
                margin: 15px 0;
            }}
            table {{
                border-collapse: collapse;
                width: 100%;
                margin: 15px 0;
            }}
            th, td {{
                border: 1px solid #ddd;
                padding: 12px;
                text-align: left;
            }}
            th {{
                background-color: #3498db;
                color: white;
            }}
            tr:nth-child(even) {{ background-color: #f9f9f9; }}
        </style>
        <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    </head>
    <body>
        <div id="content"></div>
        <script>
            const markdown = `{escaped_markdown}`;
            document.getElementById('content').innerHTML = marked.parse(markdown);
        </script>
    </body>
    </html>
    """

    return HTMLResponse(content=html_content)


@app.get("/instructions/raw", response_class=PlainTextResponse, tags=["Documentation"])
def get_instructions_raw():
    """Get the raw markdown instructions file."""
    instructions_path = "/INSTRUCTIONS.md"

    if not os.path.exists(instructions_path):
        return PlainTextResponse(content="Instructions not found", status_code=404)

    with open(instructions_path, "r") as f:
        return PlainTextResponse(content=f.read())


@app.get("/readme", response_class=HTMLResponse, tags=["Documentation"])
def get_readme():
    """View the README with full documentation including human-like scraping quirks."""
    readme_path = "/README.md"

    if not os.path.exists(readme_path):
        return HTMLResponse(content="<h1>README not found</h1><p>README.md is missing from the project root.</p>", status_code=404)

    with open(readme_path, "r") as f:
        markdown_content = f.read()

    # Escape backticks for JavaScript
    escaped_markdown = markdown_content.replace('`', '\\`').replace('$', '\\$')

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>LienHunter v2 - README</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                max-width: 1000px;
                margin: 40px auto;
                padding: 0 20px;
                line-height: 1.6;
                color: #333;
            }}
            h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
            h2 {{ color: #34495e; margin-top: 30px; border-bottom: 2px solid #ecf0f1; padding-bottom: 8px; }}
            h3 {{ color: #7f8c8d; margin-top: 20px; }}
            code {{
                background: #f4f4f4;
                padding: 2px 6px;
                border-radius: 3px;
                font-family: 'Monaco', 'Courier New', monospace;
                font-size: 0.9em;
            }}
            pre {{
                background: #2c3e50;
                color: #ecf0f1;
                padding: 15px;
                border-radius: 5px;
                overflow-x: auto;
            }}
            pre code {{
                background: transparent;
                color: #ecf0f1;
                padding: 0;
            }}
            ul {{ margin-left: 20px; }}
            li {{ margin: 8px 0; }}
            .warning {{
                background: #fff3cd;
                border-left: 4px solid #ffc107;
                padding: 12px;
                margin: 15px 0;
            }}
            .success {{
                background: #d4edda;
                border-left: 4px solid #28a745;
                padding: 12px;
                margin: 15px 0;
            }}
            .info {{
                background: #d1ecf1;
                border-left: 4px solid #17a2b8;
                padding: 12px;
                margin: 15px 0;
            }}
            table {{
                border-collapse: collapse;
                width: 100%;
                margin: 15px 0;
            }}
            th, td {{
                border: 1px solid #ddd;
                padding: 12px;
                text-align: left;
            }}
            th {{
                background-color: #3498db;
                color: white;
            }}
            tr:nth-child(even) {{ background-color: #f9f9f9; }}
            .nav {{
                background: #3498db;
                color: white;
                padding: 10px 15px;
                margin-bottom: 20px;
                border-radius: 5px;
            }}
            .nav a {{
                color: white;
                text-decoration: none;
                margin-right: 15px;
            }}
            .nav a:hover {{
                text-decoration: underline;
            }}
        </style>
        <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    </head>
    <body>
        <div class="nav">
            <a href="/docs">📚 API Docs</a>
            <a href="/readme">📖 README</a>
            <a href="/instructions">📋 Quick Start</a>
            <a href="/readme/raw">💾 Download README</a>
        </div>
        <div id="content"></div>
        <script>
            const markdown = `{escaped_markdown}`;
            document.getElementById('content').innerHTML = marked.parse(markdown);
        </script>
    </body>
    </html>
    """

    return HTMLResponse(content=html_content)


@app.get("/readme/raw", response_class=PlainTextResponse, tags=["Documentation"])
def get_readme_raw():
    """Get the raw markdown README file."""
    readme_path = "/README.md"

    if not os.path.exists(readme_path):
        return PlainTextResponse(content="README not found", status_code=404)

    with open(readme_path, "r") as f:
        return PlainTextResponse(content=f.read())


@app.get("/getting-started", response_class=HTMLResponse, tags=["Documentation"])
def get_getting_started():
    """View the Getting Started Guide - your first stop for using LienHunter v2."""
    getting_started_path = "/GETTING_STARTED.md"

    if not os.path.exists(getting_started_path):
        return HTMLResponse(content="<h1>Getting Started not found</h1>", status_code=404)

    with open(getting_started_path, "r") as f:
        markdown_content = f.read()

    escaped_markdown = markdown_content.replace('`', '\\`').replace('$', '\\$')

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>LienHunter v2 - Getting Started</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                max-width: 1000px;
                margin: 40px auto;
                padding: 0 20px;
                line-height: 1.6;
                color: #333;
            }}
            h1 {{ color: #2c3e50; border-bottom: 3px solid #27ae60; padding-bottom: 10px; }}
            h2 {{ color: #34495e; margin-top: 30px; border-bottom: 2px solid #ecf0f1; padding-bottom: 8px; }}
            h3 {{ color: #7f8c8d; margin-top: 20px; }}
            code {{
                background: #f4f4f4;
                padding: 2px 6px;
                border-radius: 3px;
                font-family: 'Monaco', 'Courier New', monospace;
                font-size: 0.9em;
            }}
            pre {{
                background: #2c3e50;
                color: #ecf0f1;
                padding: 15px;
                border-radius: 5px;
                overflow-x: auto;
            }}
            pre code {{
                background: transparent;
                color: #ecf0f1;
                padding: 0;
            }}
            table {{
                border-collapse: collapse;
                width: 100%;
                margin: 15px 0;
            }}
            th, td {{
                border: 1px solid #ddd;
                padding: 12px;
                text-align: left;
            }}
            th {{
                background-color: #27ae60;
                color: white;
            }}
            tr:nth-child(even) {{ background-color: #f9f9f9; }}
            .nav {{
                background: #27ae60;
                color: white;
                padding: 10px 15px;
                margin-bottom: 20px;
                border-radius: 5px;
            }}
            .nav a {{
                color: white;
                text-decoration: none;
                margin-right: 15px;
            }}
            .nav a:hover {{
                text-decoration: underline;
            }}
            .tip {{
                background: #d4edda;
                border-left: 4px solid #28a745;
                padding: 12px;
                margin: 15px 0;
            }}
        </style>
        <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    </head>
    <body>
        <div class="nav">
            <a href="/getting-started">🚀 Getting Started</a>
            <a href="/docs">📚 API Docs</a>
            <a href="/readme">📖 README</a>
            <a href="/instructions">📋 Quick Start</a>
        </div>
        <div id="content"></div>
        <script>
            const markdown = `{escaped_markdown}`;
            document.getElementById('content').innerHTML = marked.parse(markdown);
        </script>
    </body>
    </html>
    """

    return HTMLResponse(content=html_content)
