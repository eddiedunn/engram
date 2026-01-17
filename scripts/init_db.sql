-- Initialize PostgreSQL database for Engram
-- Run as superuser: psql -U postgres -f init_db.sql

-- Create database and user
CREATE USER engram WITH PASSWORD 'engram';
CREATE DATABASE engram OWNER engram;

-- Connect to the database and enable extensions
\c engram

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE engram TO engram;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO engram;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO engram;

-- Verify
SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';
