import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://lienuser:lienpass@localhost:3306/lienhunter")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)


def create_tables():
    """Create all tables on startup. Safe to call multiple times."""
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS calendar_events (
                id INT AUTO_INCREMENT PRIMARY KEY,
                state VARCHAR(100) NOT NULL,
                county VARCHAR(100),
                event_date DATE NOT NULL,
                event_type VARCHAR(50) NOT NULL,
                url TEXT,
                notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_state_date (state, event_date)
            )
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS scraper_configs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                state VARCHAR(100) NOT NULL,
                county VARCHAR(100) NOT NULL,
                scraper_name VARCHAR(255) NOT NULL,
                scraper_version VARCHAR(50) DEFAULT '1.0',
                last_run_at DATETIME,
                last_run_status VARCHAR(50),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uq_state_county (state, county)
            )
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS scraped_parcels (
                id INT AUTO_INCREMENT PRIMARY KEY,
                state VARCHAR(100) NOT NULL,
                county VARCHAR(100) NOT NULL,
                parcel_id VARCHAR(255) NOT NULL,
                address TEXT,
                latitude DECIMAL(10, 7),
                longitude DECIMAL(10, 7),
                full_address TEXT,
                google_maps_url VARCHAR(500),
                assessor_url VARCHAR(500),
                treasurer_url VARCHAR(500),
                source_url VARCHAR(500),
                auction_url VARCHAR(500),
                scrape_batch_id VARCHAR(100),
                billed_amount DECIMAL(10,2),
                legal_class VARCHAR(50),
                scraper_config_id INT,
                scraped_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uq_parcel (state, county, parcel_id),
                INDEX idx_state_county (state, county),
                FOREIGN KEY (scraper_config_id) REFERENCES scraper_configs(id)
            )
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS assessments (
                id INT AUTO_INCREMENT PRIMARY KEY,
                parcel_id INT NOT NULL,

                -- Capital Guardian AI output
                decision ENUM('BID','DO_NOT_BID') NULL,
                risk_score INT NULL,
                kill_switch VARCHAR(255) NULL,
                max_bid DECIMAL(10,2) NULL,
                property_type VARCHAR(100) NULL,
                ownership_type VARCHAR(100) NULL,
                critical_warning TEXT NULL,
                ai_full_response LONGTEXT NULL,
                assessed_at DATETIME NULL,
                assessment_status ENUM('pending','assessing','assessed','failed') DEFAULT 'pending',
                assessment_error TEXT NULL,

                -- Human visual checklist (Google Earth)
                review_status ENUM('pending','in_review','approved','rejected') DEFAULT 'pending',
                check_street_view TINYINT(1) DEFAULT 0,
                check_street_view_notes TEXT NULL,
                check_power_lines TINYINT(1) DEFAULT 0,
                check_topography TINYINT(1) DEFAULT 0,
                check_topography_notes TEXT NULL,
                check_water_test TINYINT(1) DEFAULT 0,
                check_water_notes TEXT NULL,
                check_access_frontage TINYINT(1) DEFAULT 0,
                check_frontage_ft INT NULL,
                check_rooftop_count TINYINT(1) DEFAULT 0,
                check_rooftop_pct INT NULL,

                -- Final boss questions
                final_legal_matches_map TINYINT(1) DEFAULT 0,
                final_hidden_structure TINYINT(1) DEFAULT 0,
                final_who_cuts_grass TEXT NULL,
                final_approved TINYINT(1) DEFAULT 0,
                reviewer_notes TEXT NULL,
                reviewed_at DATETIME NULL,

                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

                UNIQUE KEY uq_parcel_assessment (parcel_id),
                INDEX idx_decision (decision),
                INDEX idx_assessment_status (assessment_status),
                INDEX idx_review_status (review_status),
                FOREIGN KEY (parcel_id) REFERENCES scraped_parcels(id)
            )
        """))

    print("Database tables created/verified.")
