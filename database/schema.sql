-- Atheon AI Platform Database Schema
-- This schema defines the core tables for tasks, agents, results, HITL, and audit logs

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable pgcrypto for encryption functions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Enable full-text search
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create enum types
CREATE TYPE task_status AS ENUM (
    'pending',
    'in_progress',
    'waiting_approval',
    'approved',
    'rejected',
    'failed',
    'completed',
    'cancelled'
);

CREATE TYPE task_priority AS ENUM (
    'low',
    'medium',
    'high',
    'critical'
);

CREATE TYPE agent_type AS ENUM (
    'orchestrator',
    'scraper',
    'summarizer',
    'transcriber',
    'data_fetcher',
    'custom'
);

CREATE TYPE audit_action AS ENUM (
    'create',
    'update',
    'delete',
    'approve',
    'reject',
    'execute'
);

-- Tasks table - stores all tasks in the system
CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    task_type VARCHAR(100) NOT NULL,
    status task_status NOT NULL DEFAULT 'pending',
    priority task_priority NOT NULL DEFAULT 'medium',
    parameters JSONB NOT NULL DEFAULT '{}'::jsonb,
    result JSONB,
    error_message TEXT,
    requires_approval BOOLEAN NOT NULL DEFAULT FALSE,
    approved_by UUID,
    approved_at TIMESTAMP WITH TIME ZONE,
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,
    parent_task_id UUID,
    scheduled_for TIMESTAMP WITH TIME ZONE,
    created_by UUID,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    completed_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT fk_parent_task FOREIGN KEY (parent_task_id) REFERENCES tasks(id) ON DELETE SET NULL
);

-- Create indexes for tasks
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_priority ON tasks(priority);
CREATE INDEX idx_tasks_created_at ON tasks(created_at);
CREATE INDEX idx_tasks_parent_task_id ON tasks(parent_task_id);
CREATE INDEX idx_tasks_task_type ON tasks(task_type);
CREATE INDEX idx_tasks_requires_approval ON tasks(requires_approval);
CREATE INDEX idx_tasks_scheduled_for ON tasks(scheduled_for);

-- Enable full-text search on task title and description
CREATE INDEX idx_tasks_title_description_trgm ON tasks USING GIN (
    (title || ' ' || COALESCE(description, '')) gin_trgm_ops
);

-- Add trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_tasks_updated_at
BEFORE UPDATE ON tasks
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

-- Agents table - stores information about available agents
CREATE TABLE agents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    agent_type agent_type NOT NULL,
    description TEXT,
    capabilities JSONB NOT NULL DEFAULT '{}'::jsonb,
    configuration JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_heartbeat TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Create indexes for agents
CREATE INDEX idx_agents_type ON agents(agent_type);
CREATE INDEX idx_agents_is_active ON agents(is_active);
CREATE INDEX idx_agents_last_heartbeat ON agents(last_heartbeat);

-- Add trigger to update updated_at timestamp
CREATE TRIGGER update_agents_updated_at
BEFORE UPDATE ON agents
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

-- Agent tasks - maps tasks to the agents that processed them
CREATE TABLE agent_tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    completed_at TIMESTAMP WITH TIME ZONE,
    success BOOLEAN,
    result JSONB,
    error_message TEXT,
    processing_time INTERVAL,
    UNIQUE (agent_id, task_id, started_at)
);

-- Create indexes for agent_tasks
CREATE INDEX idx_agent_tasks_agent_id ON agent_tasks(agent_id);
CREATE INDEX idx_agent_tasks_task_id ON agent_tasks(task_id);
CREATE INDEX idx_agent_tasks_started_at ON agent_tasks(started_at);
CREATE INDEX idx_agent_tasks_success ON agent_tasks(success);

-- HITL (Human-in-the-loop) table - stores information about human interactions
CREATE TABLE hitl_interactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    user_id UUID NOT NULL,
    interaction_type VARCHAR(50) NOT NULL,
    prompt TEXT,
    response TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Create indexes for hitl_interactions
CREATE INDEX idx_hitl_interactions_task_id ON hitl_interactions(task_id);
CREATE INDEX idx_hitl_interactions_user_id ON hitl_interactions(user_id);
CREATE INDEX idx_hitl_interactions_created_at ON hitl_interactions(created_at);

-- Users table - stores information about users who can interact with the system
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(50) NOT NULL DEFAULT 'user',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    last_login TIMESTAMP WITH TIME ZONE
);

-- Create indexes for users
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);

-- Add trigger to update updated_at timestamp
CREATE TRIGGER update_users_updated_at
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

-- Audit logs - tracks all important changes in the system
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID,
    entity_type VARCHAR(50) NOT NULL,
    entity_id UUID NOT NULL,
    action audit_action NOT NULL,
    previous_state JSONB,
    new_state JSONB,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

-- Create indexes for audit_logs
CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_entity_type_id ON audit_logs(entity_type, entity_id);
CREATE INDEX idx_audit_logs_action ON audit_logs(action);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at);

-- API keys - for external integrations
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    key_hash TEXT NOT NULL,
    permissions JSONB NOT NULL DEFAULT '{}'::jsonb,
    expires_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_used_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    UNIQUE (user_id, name)
);

-- Create indexes for api_keys
CREATE INDEX idx_api_keys_user_id ON api_keys(user_id);
CREATE INDEX idx_api_keys_is_active ON api_keys(is_active);
CREATE INDEX idx_api_keys_expires_at ON api_keys(expires_at);

-- Add trigger to update updated_at timestamp
CREATE TRIGGER update_api_keys_updated_at
BEFORE UPDATE ON api_keys
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

-- Function to generate a new API key
CREATE OR REPLACE FUNCTION generate_api_key(
    p_user_id UUID,
    p_name VARCHAR,
    p_permissions JSONB DEFAULT '{}'::jsonb,
    p_expires_at TIMESTAMP WITH TIME ZONE DEFAULT NULL
) RETURNS TABLE (
    key_id UUID,
    key_value TEXT
) AS $$
DECLARE
    v_key_value TEXT;
    v_key_id UUID;
BEGIN
    -- Generate a random API key
    v_key_value := encode(gen_random_bytes(24), 'hex');

    -- Insert the hashed key into the table
    INSERT INTO api_keys (
        user_id,
        name,
        key_hash,
        permissions,
        expires_at
    ) VALUES (
        p_user_id,
        p_name,
        crypt(v_key_value, gen_salt('bf')),
        p_permissions,
        p_expires_at
    ) RETURNING id INTO v_key_id;

    -- Return the key information (only time the plain key is available)
    RETURN QUERY SELECT v_key_id, v_key_value;
END;
$$ LANGUAGE plpgsql;

-- Function to validate an API key
CREATE OR REPLACE FUNCTION validate_api_key(p_key_value TEXT) RETURNS UUID AS $$
DECLARE
    v_user_id UUID;
BEGIN
    -- Update the last_used_at timestamp and return the user_id if valid
    UPDATE api_keys
    SET last_used_at = now()
    WHERE key_hash = crypt(p_key_value, key_hash)
    AND (expires_at IS NULL OR expires_at > now())
    AND is_active = TRUE
    RETURNING user_id INTO v_user_id;

    RETURN v_user_id;
END;
$$ LANGUAGE plpgsql;

-- Task history - stores each state change of a task
CREATE TABLE task_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    previous_status task_status,
    new_status task_status NOT NULL,
    agent_id UUID REFERENCES agents(id) ON DELETE SET NULL,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Create indexes for task_history
CREATE INDEX idx_task_history_task_id ON task_history(task_id);
CREATE INDEX idx_task_history_previous_status ON task_history(previous_status);
CREATE INDEX idx_task_history_new_status ON task_history(new_status);
CREATE INDEX idx_task_history_created_at ON task_history(created_at);

-- Trigger to automatically record task history on status change
CREATE OR REPLACE FUNCTION record_task_status_change()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status IS DISTINCT FROM NEW.status THEN
        INSERT INTO task_history (
            task_id,
            previous_status,
            new_status,
            metadata
        ) VALUES (
            NEW.id,
            OLD.status,
            NEW.status,
            jsonb_build_object(
                'retry_count', NEW.retry_count,
                'updated_at', NEW.updated_at
            )
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER track_task_status_changes
AFTER UPDATE ON tasks
FOR EACH ROW
EXECUTE FUNCTION record_task_status_change();

-- Example: create a function to get tasks with their agent details
CREATE OR REPLACE FUNCTION get_tasks_with_agents(
    p_limit INTEGER DEFAULT 100,
    p_offset INTEGER DEFAULT 0,
    p_status task_status DEFAULT NULL,
    p_task_type VARCHAR DEFAULT NULL
) RETURNS TABLE (
    task_id UUID,
    title VARCHAR,
    task_type VARCHAR,
    status task_status,
    created_at TIMESTAMP WITH TIME ZONE,
    agent_name VARCHAR,
    agent_type agent_type,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        t.id AS task_id,
        t.title,
        t.task_type,
        t.status,
        t.created_at,
        a.name AS agent_name,
        a.agent_type,
        at.started_at,
        at.completed_at
    FROM tasks t
    LEFT JOIN agent_tasks at ON t.id = at.task_id
    LEFT JOIN agents a ON at.agent_id = a.id
    WHERE (p_status IS NULL OR t.status = p_status)
    AND (p_task_type IS NULL OR t.task_type = p_task_type)
    ORDER BY t.created_at DESC
    LIMIT p_limit
    OFFSET p_offset;
END;
$$ LANGUAGE plpgsql;

-- Views for common queries

-- Active tasks view
CREATE OR REPLACE VIEW active_tasks AS
SELECT
    t.id,
    t.title,
    t.task_type,
    t.status,
    t.priority,
    t.created_at,
    t.updated_at,
    t.requires_approval,
    a.name AS current_agent
FROM tasks t
LEFT JOIN agent_tasks at ON t.id = at.task_id AND at.completed_at IS NULL
LEFT JOIN agents a ON at.agent_id = a.id
WHERE t.status IN ('pending', 'in_progress', 'waiting_approval')
ORDER BY
    CASE
        WHEN t.priority = 'critical' THEN 1
        WHEN t.priority = 'high' THEN 2
        WHEN t.priority = 'medium' THEN 3
        ELSE 4
    END,
    t.created_at;

-- Tasks pending approval view
CREATE OR REPLACE VIEW tasks_pending_approval AS
SELECT
    t.id,
    t.title,
    t.task_type,
    t.description,
    t.parameters,
    t.result,
    t.created_at,
    t.updated_at
FROM tasks t
WHERE t.status = 'waiting_approval'
ORDER BY t.updated_at;

-- Agent performance view
CREATE OR REPLACE VIEW agent_performance AS
SELECT
    a.id AS agent_id,
    a.name AS agent_name,
    a.agent_type,
    COUNT(at.id) AS total_tasks,
    COUNT(at.id) FILTER (WHERE at.success = TRUE) AS successful_tasks,
    COUNT(at.id) FILTER (WHERE at.success = FALSE) AS failed_tasks,
    ROUND(COUNT(at.id) FILTER (WHERE at.success = TRUE) * 100.0 / NULLIF(COUNT(at.id), 0), 2) AS success_rate,
    AVG(EXTRACT(EPOCH FROM at.processing_time)) FILTER (WHERE at.success = TRUE) AS avg_processing_time_seconds
FROM agents a
LEFT JOIN agent_tasks at ON a.id = at.agent_id
GROUP BY a.id, a.name, a.agent_type
ORDER BY a.name;

-- Initialize with a default admin user
-- Password: admin123 (this is just an example - use a secure password in production)
INSERT INTO users (
    username,
    email,
    password_hash,
    full_name,
    role
) VALUES (
    'admin',
    'admin@atheon.ai',
    crypt('admin123', gen_salt('bf')),
    'Atheon Administrator',
    'admin'
);

-- Insert default agents
INSERT INTO agents (name, agent_type, description, capabilities) VALUES
('orchestrator', 'orchestrator', 'Main orchestration service', '{"can_assign_tasks": true, "can_validate_results": true}'::jsonb),
('scraper', 'scraper', 'Web scraping agent', '{"can_scrape_html": true, "can_handle_javascript": true}'::jsonb),
('summarizer', 'summarizer', 'Text summarization agent', '{"can_summarize_text": true, "can_extract_keywords": true}'::jsonb),
('data-fetcher', 'data_fetcher', 'External API data fetching agent', '{"can_fetch_api_data": true, "can_format_responses": true}'::jsonb);

-- Create sample tasks for testing
INSERT INTO tasks (title, description, task_type, status, requires_approval)
VALUES
('Scrape news articles', 'Collect recent news from technology websites', 'web_scraping', 'pending', FALSE),
('Summarize earnings report', 'Create a summary of the Q3 earnings report', 'summarization', 'pending', TRUE),
('Fetch weather data', 'Get weather forecast for next week', 'api_fetch', 'pending', FALSE);