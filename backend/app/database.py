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
                reminder_7d_sent TINYINT DEFAULT 0,
                reminder_3d_sent TINYINT DEFAULT 0,
                reminder_1d_sent TINYINT DEFAULT 0,
                reminder_0d_sent TINYINT DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_state_date (state, event_date)
            )
        """))
        # Migrations for existing deployments
        for col in ["reminder_7d_sent", "reminder_3d_sent", "reminder_1d_sent", "reminder_0d_sent"]:
            try:
                conn.execute(text(f"ALTER TABLE calendar_events ADD COLUMN {col} TINYINT DEFAULT 0"))
            except Exception:
                pass

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
                street_view_url VARCHAR(500),
                assessor_url VARCHAR(500),
                treasurer_url VARCHAR(500),
                source_url VARCHAR(500),
                auction_url VARCHAR(500),
                scrape_batch_id VARCHAR(100),
                lot_size_acres DECIMAL(10, 4),
                lot_size_sqft INT,
                zoning_code VARCHAR(50),
                zoning_description VARCHAR(255),
                assessed_land_value DECIMAL(12, 2),
                assessed_improvement_value DECIMAL(12, 2),
                assessed_total_value DECIMAL(12, 2),
                legal_description TEXT,
                zillow_url VARCHAR(500),
                realtor_url VARCHAR(500),
                billed_amount DECIMAL(10,2),
                legal_class VARCHAR(255),
                owner_name VARCHAR(255),
                owner_mailing_address TEXT,
                scraper_config_id INT,
                scraped_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uq_parcel (state, county, parcel_id),
                INDEX idx_state_county (state, county),
                INDEX idx_owner_name (owner_name),
                FOREIGN KEY (scraper_config_id) REFERENCES scraper_configs(id)
            )
        """))

        # Idempotent migrations for running deployments that have the old schema.
        # Note: MySQL does not support IF NOT EXISTS in ALTER TABLE — rely on try/except instead.
        migrations = [
            "ALTER TABLE scraped_parcels ADD COLUMN street_view_url VARCHAR(500) NULL",
            "ALTER TABLE scraped_parcels ADD COLUMN lot_size_acres DECIMAL(10,4) NULL",
            "ALTER TABLE scraped_parcels ADD COLUMN lot_size_sqft INT NULL",
            "ALTER TABLE scraped_parcels ADD COLUMN zoning_code VARCHAR(50) NULL",
            "ALTER TABLE scraped_parcels ADD COLUMN zoning_description VARCHAR(255) NULL",
            "ALTER TABLE scraped_parcels ADD COLUMN assessed_land_value DECIMAL(12,2) NULL",
            "ALTER TABLE scraped_parcels ADD COLUMN assessed_improvement_value DECIMAL(12,2) NULL",
            "ALTER TABLE scraped_parcels ADD COLUMN assessed_total_value DECIMAL(12,2) NULL",
            "ALTER TABLE scraped_parcels ADD COLUMN legal_description TEXT NULL",
            "ALTER TABLE scraped_parcels ADD COLUMN zillow_url VARCHAR(500) NULL",
            "ALTER TABLE scraped_parcels ADD COLUMN realtor_url VARCHAR(500) NULL",
            "ALTER TABLE scraped_parcels ADD COLUMN owner_name VARCHAR(255) NULL",
            "ALTER TABLE scraped_parcels ADD COLUMN owner_mailing_address TEXT NULL",
            # Tax payment history fields (from treasurer &action=tx page)
            "ALTER TABLE scraped_parcels ADD COLUMN years_delinquent INT NULL",
            "ALTER TABLE scraped_parcels ADD COLUMN prior_liens_count INT NULL",
            "ALTER TABLE scraped_parcels ADD COLUMN total_outstanding DECIMAL(12,2) NULL",
            "ALTER TABLE scraped_parcels ADD COLUMN first_delinquent_year INT NULL",
            "ALTER TABLE scraped_parcels MODIFY COLUMN legal_class VARCHAR(255)",
        ]
        for migration in migrations:
            try:
                conn.execute(text(migration))
            except Exception:
                pass  # Column already exists or DB doesn't support IF NOT EXISTS

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

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS scraper_checkpoints (
                id INT AUTO_INCREMENT PRIMARY KEY,
                state VARCHAR(100) NOT NULL,
                county VARCHAR(100) NOT NULL,
                last_page_completed INT NOT NULL DEFAULT 0,
                total_parcels_scraped INT NOT NULL DEFAULT 0,
                total_parcels_available INT NOT NULL DEFAULT 0,
                job_id VARCHAR(100),
                status ENUM('in_progress','completed','failed') DEFAULT 'in_progress',
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uq_checkpoint (state, county)
            )
        """))
        try:
            conn.execute(text("ALTER TABLE scraper_checkpoints ADD COLUMN total_parcels_available INT NOT NULL DEFAULT 0"))
        except Exception:
            pass

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS system_settings (
                key_name VARCHAR(100) PRIMARY KEY,
                value VARCHAR(500) NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """))
        # Default: notifications on
        conn.execute(text("""
            INSERT IGNORE INTO system_settings (key_name, value)
            VALUES ('notifications_enabled', 'true')
        """))

    print("Database tables created/verified.")
