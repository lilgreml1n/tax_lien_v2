from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse
from app.database import create_tables
from app.routers.calendar import router as calendar_router
from app.routers.scrapers import router as scrapers_router
from app.routers.review import router as review_router
import os

app = FastAPI(
    title="LienHunter v2",
    description="Tax Lien Investment Platform - Scrape, Assess, Review, Buy",
    version="2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
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


@app.get("/health")
def health():
    return {"status": "ok", "version": "2.0"}


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
