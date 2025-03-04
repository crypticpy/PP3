-- PolicyPulse PostgreSQL Database Schema
-- This script creates the complete database schema for the PolicyPulse application
-- for tracking and analyzing legislation with focus on public health and local government impacts

-- Enable required PostgreSQL extensions
CREATE EXTENSION IF NOT EXISTS pg_trgm;    -- For trigram-based text search
CREATE EXTENSION IF NOT EXISTS unaccent;   -- For accent-insensitive search

-- Create custom types (ENUMs)
CREATE TYPE data_source_enum AS ENUM ('legiscan', 'congress_gov', 'other');
CREATE TYPE govt_type_enum AS ENUM ('federal', 'state', 'county', 'city');
CREATE TYPE bill_status_enum AS ENUM ('new', 'introduced', 'updated', 'passed', 'defeated', 'vetoed', 'enacted', 'pending');
CREATE TYPE impact_level_enum AS ENUM ('low', 'moderate', 'high', 'critical');
CREATE TYPE impact_category_enum AS ENUM ('public_health', 'local_gov', 'economic', 'environmental', 'education', 'infrastructure', 'healthcare', 'social_services', 'justice');
CREATE TYPE amendment_status_enum AS ENUM ('proposed', 'adopted', 'rejected', 'withdrawn');
CREATE TYPE notification_type_enum AS ENUM ('high_priority', 'new_bill', 'status_change', 'analysis_complete');
CREATE TYPE sync_status_enum AS ENUM ('pending', 'in_progress', 'completed', 'failed', 'partial');

-- Create tables with all relationships
-- Base model with audit fields (used as a template for other tables)

-- Users and Preferences
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR UNIQUE NOT NULL,
    name VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    role VARCHAR(20) DEFAULT 'user',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by VARCHAR(50),
    updated_by VARCHAR(50)
);

CREATE TABLE user_preferences (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    keywords JSONB,
    health_focus JSONB,
    local_govt_focus JSONB,
    regions JSONB,
    default_view VARCHAR(20) DEFAULT 'all',
    items_per_page INTEGER DEFAULT 25 CHECK (items_per_page > 0),
    sort_by VARCHAR(20) DEFAULT 'updated_at',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by VARCHAR(50),
    updated_by VARCHAR(50)
);

CREATE TABLE search_history (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    query VARCHAR,
    filters JSONB,
    results JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by VARCHAR(50),
    updated_by VARCHAR(50)
);

CREATE TABLE alert_preferences (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    active BOOLEAN DEFAULT TRUE,
    alert_channels JSONB,
    custom_keywords JSONB,
    ignore_list JSONB,
    alert_rules JSONB,
    health_threshold INTEGER DEFAULT 60 CHECK (health_threshold BETWEEN 0 AND 100),
    local_govt_threshold INTEGER DEFAULT 60 CHECK (local_govt_threshold BETWEEN 0 AND 100),
    notify_on_new BOOLEAN DEFAULT FALSE,
    notify_on_update BOOLEAN DEFAULT FALSE,
    notify_on_analysis BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by VARCHAR(50),
    updated_by VARCHAR(50)
);

-- Legislation and Related Tables
CREATE TABLE legislation (
    id SERIAL PRIMARY KEY,
    external_id VARCHAR(50) NOT NULL,
    data_source data_source_enum NOT NULL,
    govt_type govt_type_enum NOT NULL,
    govt_source VARCHAR(100) NOT NULL,
    bill_number VARCHAR(50) NOT NULL,
    bill_type VARCHAR(50),
    title TEXT NOT NULL,
    description TEXT,
    bill_status bill_status_enum DEFAULT 'new',
    url TEXT,
    state_link TEXT,
    bill_introduced_date TIMESTAMP,
    bill_last_action_date TIMESTAMP,
    bill_status_date TIMESTAMP,
    last_api_check TIMESTAMP DEFAULT NOW(),
    change_hash VARCHAR(50),
    raw_api_response JSONB,
    search_vector tsvector,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by VARCHAR(50),
    updated_by VARCHAR(50),
    CONSTRAINT unique_bill_identifier UNIQUE (data_source, govt_source, bill_number)
);

CREATE TABLE legislation_analysis (
    id SERIAL PRIMARY KEY,
    legislation_id INTEGER NOT NULL REFERENCES legislation(id) ON DELETE CASCADE,
    analysis_version INTEGER NOT NULL DEFAULT 1 CHECK (analysis_version > 0),
    version_tag VARCHAR(50),
    previous_version_id INTEGER REFERENCES legislation_analysis(id),
    changes_from_previous JSONB,
    analysis_date TIMESTAMP NOT NULL DEFAULT NOW(),
    impact_category impact_category_enum,
    impact impact_level_enum,
    summary TEXT,
    key_points JSONB,
    public_health_impacts JSONB,
    local_gov_impacts JSONB,
    economic_impacts JSONB,
    environmental_impacts JSONB,
    education_impacts JSONB,
    infrastructure_impacts JSONB,
    stakeholder_impacts JSONB,
    recommended_actions JSONB,
    immediate_actions JSONB,
    resource_needs JSONB,
    raw_analysis JSONB,
    model_version VARCHAR(50),
    confidence_score FLOAT,
    processing_time INTEGER,
    processing_metadata JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by VARCHAR(50),
    updated_by VARCHAR(50),
    CONSTRAINT unique_analysis_version UNIQUE (legislation_id, analysis_version)
);

CREATE TABLE legislation_text (
    id SERIAL PRIMARY KEY,
    legislation_id INTEGER NOT NULL REFERENCES legislation(id) ON DELETE CASCADE,
    version_num INTEGER NOT NULL DEFAULT 1 CHECK (version_num > 0),
    text_type VARCHAR(50),
    text_content TEXT,
    binary_content BYTEA, -- For binary documents (PDF, DOC, etc)
    text_hash VARCHAR(50),
    text_date TIMESTAMP,
    text_metadata JSONB,
    is_binary BOOLEAN DEFAULT FALSE,
    content_type VARCHAR(100),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by VARCHAR(50),
    updated_by VARCHAR(50),
    CONSTRAINT unique_text_version UNIQUE (legislation_id, version_num)
);

CREATE TABLE legislation_sponsors (
    id SERIAL PRIMARY KEY,
    legislation_id INTEGER NOT NULL REFERENCES legislation(id) ON DELETE CASCADE,
    sponsor_external_id VARCHAR(50),
    sponsor_name VARCHAR(255) NOT NULL,
    sponsor_title VARCHAR(100),
    sponsor_state VARCHAR(50),
    sponsor_party VARCHAR(50),
    sponsor_type VARCHAR(50),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by VARCHAR(50),
    updated_by VARCHAR(50)
);

CREATE TABLE amendments (
    id SERIAL PRIMARY KEY,
    amendment_id VARCHAR(50) NOT NULL,
    legislation_id INTEGER NOT NULL REFERENCES legislation(id) ON DELETE CASCADE,
    adopted BOOLEAN DEFAULT FALSE,
    status amendment_status_enum DEFAULT 'proposed',
    amendment_date TIMESTAMP,
    title VARCHAR(255),
    description TEXT,
    amendment_hash VARCHAR(50),
    amendment_text TEXT,
    binary_content BYTEA, -- For binary documents
    amendment_url VARCHAR(255),
    state_link VARCHAR(255),
    chamber VARCHAR(50),
    sponsor_info JSONB,
    text_metadata JSONB,
    is_binary_text BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by VARCHAR(50),
    updated_by VARCHAR(50)
);

CREATE TABLE legislation_priorities (
    id SERIAL PRIMARY KEY,
    legislation_id INTEGER NOT NULL REFERENCES legislation(id) ON DELETE CASCADE,
    public_health_relevance INTEGER DEFAULT 0 CHECK (public_health_relevance BETWEEN 0 AND 100),
    local_govt_relevance INTEGER DEFAULT 0 CHECK (local_govt_relevance BETWEEN 0 AND 100),
    overall_priority INTEGER DEFAULT 0 CHECK (overall_priority BETWEEN 0 AND 100),
    auto_categorized BOOLEAN DEFAULT FALSE,
    auto_categories JSONB,
    manually_reviewed BOOLEAN DEFAULT FALSE,
    manual_priority INTEGER DEFAULT 0 CHECK (manual_priority BETWEEN 0 AND 100),
    reviewer_notes TEXT,
    review_date TIMESTAMP,
    should_notify BOOLEAN DEFAULT FALSE,
    notification_sent BOOLEAN DEFAULT FALSE,
    notification_date TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by VARCHAR(50),
    updated_by VARCHAR(50)
);

CREATE TABLE impact_ratings (
    id SERIAL PRIMARY KEY,
    legislation_id INTEGER NOT NULL REFERENCES legislation(id) ON DELETE CASCADE,
    impact_category impact_category_enum NOT NULL,
    impact_level impact_level_enum NOT NULL,
    impact_description TEXT,
    affected_entities JSONB,
    confidence_score FLOAT CHECK (confidence_score BETWEEN 0 AND 1),
    is_ai_generated BOOLEAN DEFAULT TRUE,
    reviewed_by VARCHAR(100),
    review_date TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by VARCHAR(50),
    updated_by VARCHAR(50)
);

CREATE TABLE implementation_requirements (
    id SERIAL PRIMARY KEY,
    legislation_id INTEGER NOT NULL REFERENCES legislation(id) ON DELETE CASCADE,
    requirement_type VARCHAR(50) NOT NULL,
    description TEXT NOT NULL,
    estimated_cost VARCHAR(100),
    funding_provided BOOLEAN DEFAULT FALSE,
    implementation_deadline TIMESTAMP,
    entity_responsible VARCHAR(100),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by VARCHAR(50),
    updated_by VARCHAR(50)
);

CREATE TABLE alert_history (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    legislation_id INTEGER NOT NULL REFERENCES legislation(id) ON DELETE CASCADE,
    alert_type notification_type_enum NOT NULL,
    alert_content TEXT,
    delivery_status VARCHAR(50),
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by VARCHAR(50),
    updated_by VARCHAR(50)
);

-- Sync Metadata and Tracking
CREATE TABLE sync_metadata (
    id SERIAL PRIMARY KEY,
    last_sync TIMESTAMP NOT NULL DEFAULT NOW(),
    last_successful_sync TIMESTAMP,
    status sync_status_enum DEFAULT 'pending' NOT NULL,
    sync_type VARCHAR(50),
    new_bills INTEGER DEFAULT 0,
    bills_updated INTEGER DEFAULT 0,
    errors JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by VARCHAR(50),
    updated_by VARCHAR(50)
);

CREATE TABLE sync_errors (
    id SERIAL PRIMARY KEY,
    sync_id INTEGER NOT NULL REFERENCES sync_metadata(id) ON DELETE CASCADE,
    error_type VARCHAR(50),
    error_message TEXT,
    stack_trace TEXT,
    error_time TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by VARCHAR(50),
    updated_by VARCHAR(50)
);

-- Create indexes for performance optimization
CREATE INDEX idx_legislation_status ON legislation(bill_status);
CREATE INDEX idx_legislation_dates ON legislation(bill_introduced_date, bill_last_action_date);
CREATE INDEX idx_legislation_change ON legislation(change_hash);
CREATE INDEX idx_legislation_search ON legislation USING gin(search_vector);
CREATE INDEX idx_amendments_legislation ON amendments(legislation_id);
CREATE INDEX idx_amendments_date ON amendments(amendment_date);
CREATE INDEX idx_priority_health ON legislation_priorities(public_health_relevance);
CREATE INDEX idx_priority_local_govt ON legislation_priorities(local_govt_relevance);
CREATE INDEX idx_priority_overall ON legislation_priorities(overall_priority);

-- Create functions and triggers for full-text search
CREATE OR REPLACE FUNCTION legislation_search_update_trigger() RETURNS trigger AS $$
BEGIN
  NEW.search_vector = 
    setweight(to_tsvector('english', coalesce(NEW.title, '')), 'A') ||
    setweight(to_tsvector('english', coalesce(NEW.description, '')), 'B');
  RETURN NEW;
END
$$ LANGUAGE plpgsql;

CREATE TRIGGER tsvector_update BEFORE INSERT OR UPDATE
ON legislation FOR EACH ROW EXECUTE FUNCTION legislation_search_update_trigger();

-- Create function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_modified_column() RETURNS trigger AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply the update_modified_column trigger to all tables
CREATE TRIGGER update_users_modtime BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_modified_column();
CREATE TRIGGER update_user_preferences_modtime BEFORE UPDATE ON user_preferences FOR EACH ROW EXECUTE FUNCTION update_modified_column();
CREATE TRIGGER update_search_history_modtime BEFORE UPDATE ON search_history FOR EACH ROW EXECUTE FUNCTION update_modified_column();
CREATE TRIGGER update_alert_preferences_modtime BEFORE UPDATE ON alert_preferences FOR EACH ROW EXECUTE FUNCTION update_modified_column();
CREATE TRIGGER update_legislation_modtime BEFORE UPDATE ON legislation FOR EACH ROW EXECUTE FUNCTION update_modified_column();
CREATE TRIGGER update_legislation_analysis_modtime BEFORE UPDATE ON legislation_analysis FOR EACH ROW EXECUTE FUNCTION update_modified_column();
CREATE TRIGGER update_legislation_text_modtime BEFORE UPDATE ON legislation_text FOR EACH ROW EXECUTE FUNCTION update_modified_column();
CREATE TRIGGER update_legislation_sponsors_modtime BEFORE UPDATE ON legislation_sponsors FOR EACH ROW EXECUTE FUNCTION update_modified_column();
CREATE TRIGGER update_amendments_modtime BEFORE UPDATE ON amendments FOR EACH ROW EXECUTE FUNCTION update_modified_column();
CREATE TRIGGER update_legislation_priorities_modtime BEFORE UPDATE ON legislation_priorities FOR EACH ROW EXECUTE FUNCTION update_modified_column();
CREATE TRIGGER update_impact_ratings_modtime BEFORE UPDATE ON impact_ratings FOR EACH ROW EXECUTE FUNCTION update_modified_column();
CREATE TRIGGER update_implementation_requirements_modtime BEFORE UPDATE ON implementation_requirements FOR EACH ROW EXECUTE FUNCTION update_modified_column();
CREATE TRIGGER update_alert_history_modtime BEFORE UPDATE ON alert_history FOR EACH ROW EXECUTE FUNCTION update_modified_column();
CREATE TRIGGER update_sync_metadata_modtime BEFORE UPDATE ON sync_metadata FOR EACH ROW EXECUTE FUNCTION update_modified_column();
CREATE TRIGGER update_sync_errors_modtime BEFORE UPDATE ON sync_errors FOR EACH ROW EXECUTE FUNCTION update_modified_column();

-- Grant privileges
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO admin;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO admin;

-- Create initial admin user
INSERT INTO users (email, name, role, created_at, updated_at)
VALUES ('admin@policypulse.org', 'System Administrator', 'admin', NOW(), NOW());

-- Create initial alert preference for admin
INSERT INTO alert_preferences (user_id, email, active, health_threshold, local_govt_threshold)
VALUES (1, 'admin@policypulse.org', TRUE, 70, 70);

-- Create initial sync metadata record
INSERT INTO sync_metadata (sync_type, status, last_sync)
VALUES ('initial', 'completed', NOW());

-- Confirm completion
SELECT 'PolicyPulse database schema created successfully!' AS result;