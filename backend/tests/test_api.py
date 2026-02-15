"""Unit tests for LienHunter v2 API."""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


# ==================== Health ====================

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["version"] == "2.0"


# ==================== Calendar ====================

def test_create_calendar_event():
    r = client.post("/calendar/events", json={
        "state": "Arizona",
        "county": "Apache",
        "event_date": "2026-03-15",
        "event_type": "auction",
        "notes": "Test auction"
    })
    assert r.status_code == 200
    assert r.json()["status"] == "created"


def test_list_calendar_events():
    r = client.get("/calendar/events?state=Arizona")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_this_month():
    r = client.get("/calendar/this-month")
    assert r.status_code == 200


def test_next_month():
    r = client.get("/calendar/next-month")
    assert r.status_code == 200


# ==================== Scraper Config ====================

def test_create_scraper_config():
    r = client.post("/scrapers/config", json={
        "state": "Arizona",
        "county": "Apache",
        "scraper_name": "app.scrapers.arizona.apache.ApacheScraper",
        "scraper_version": "2.0"
    })
    assert r.status_code == 200
    assert r.json()["status"] in ("created", "updated")


def test_list_scraper_configs():
    r = client.get("/scrapers/config")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ==================== Scrape Endpoint ====================

def test_scrape_missing_config():
    r = client.post("/scrapers/scrape/Fake/County")
    assert r.status_code == 404


def test_scrape_returns_job():
    # Ensure config exists first
    client.post("/scrapers/config", json={
        "state": "Arizona",
        "county": "Apache",
        "scraper_name": "app.scrapers.arizona.apache.ApacheScraper"
    })
    r = client.post("/scrapers/scrape/Arizona/Apache?limit=1")
    assert r.status_code == 200
    data = r.json()
    assert "job_id" in data
    assert data["status"] == "scraping"


# ==================== Assess Endpoint ====================

def test_assess_no_parcels():
    r = client.post("/scrapers/assess/Fake/County")
    assert r.status_code == 404


# ==================== Results ====================

def test_get_parcels():
    r = client.get("/scrapers/parcels/Arizona/Apache")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_unassessed():
    r = client.get("/scrapers/unassessed/Arizona/Apache")
    assert r.status_code == 200
    assert "unassessed_count" in r.json()


def test_bids():
    r = client.get("/scrapers/bids")
    assert r.status_code == 200


def test_rejects():
    r = client.get("/scrapers/rejects")
    assert r.status_code == 200


def test_pipeline_status():
    r = client.get("/scrapers/pipeline-status/Arizona/Apache")
    assert r.status_code == 200
    data = r.json()
    assert "scraped" in data
    assert "assessed" in data
    assert "bids" in data


# ==================== Review ====================

def test_review_queue():
    r = client.get("/review/queue")
    assert r.status_code == 200


def test_approved():
    r = client.get("/review/approved")
    assert r.status_code == 200


def test_checklist_not_found():
    r = client.put("/review/checklist/99999", json={"check_street_view": True})
    assert r.status_code == 404


def test_final_approve_not_found():
    r = client.put("/review/final-approve/99999", json={"final_legal_matches_map": True})
    assert r.status_code == 404
