-- PostgreSQL initialization script for onderwijsdata-chat
-- Run this after CloudNativePG cluster is ready

-- Create application user (if not exists)
DO $$
BEGIN
  CREATE USER onderwijsdata_chat WITH PASSWORD 'change_me_in_production';
EXCEPTION WHEN DUPLICATE_OBJECT THEN
  NULL;
END
$$;

-- Create database
CREATE DATABASE onderwijsdata_chat OWNER onderwijsdata_chat;

-- Grant privileges
GRANT CREATE ON DATABASE onderwijsdata_chat TO onderwijsdata_chat;

-- Connect to the database and create tables
\c onderwijsdata_chat

-- Ensure schema ownership
ALTER SCHEMA public OWNER TO onderwijsdata_chat;

-- Create tables
CREATE TABLE IF NOT EXISTS conversations (
  id        TEXT    NOT NULL,
  username  TEXT    NOT NULL,
  title     TEXT    NOT NULL,
  timestamp INTEGER NOT NULL,
  messages  TEXT    NOT NULL,
  PRIMARY KEY (id, username)
);

CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(username, timestamp DESC);

CREATE TABLE IF NOT EXISTS workbooks (
  id             TEXT NOT NULL,
  username       TEXT NOT NULL,
  title          TEXT NOT NULL,
  description    TEXT NOT NULL DEFAULT '',
  messages       TEXT,
  figures        TEXT,
  instelling     TEXT,
  html_content   TEXT,
  dashboard_spec TEXT,
  created_at     TEXT NOT NULL,
  PRIMARY KEY (id, username)
);

CREATE INDEX IF NOT EXISTS idx_wb_user ON workbooks(username, created_at DESC);

-- Set ownership
ALTER TABLE conversations OWNER TO onderwijsdata_chat;
ALTER TABLE workbooks OWNER TO onderwijsdata_chat;
ALTER INDEX idx_conv_user OWNER TO onderwijsdata_chat;
ALTER INDEX idx_wb_user OWNER TO onderwijsdata_chat;

-- Grant table permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON conversations TO onderwijsdata_chat;
GRANT SELECT, INSERT, UPDATE, DELETE ON workbooks TO onderwijsdata_chat;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO onderwijsdata_chat;
