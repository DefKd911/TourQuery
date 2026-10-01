-- Database users for TourQuery, least privilege first. Run as the database
-- owner after schema.sql. Passwords are set separately and live only in .env.
--
--   owner (neondb_owner)  -> schema changes and seeding scripts only
--   tourquery_readonly    -> the agent's queries: SELECT on tennis tables, 5s timeout
--   tourquery_memory      -> conversation memory: its own schema, no tennis tables

-- Agent query user (Step 2, timeout added in Step 6).
CREATE ROLE tourquery_readonly WITH LOGIN PASSWORD :'readonly_password';
GRANT CONNECT ON DATABASE neondb TO tourquery_readonly;
GRANT USAGE ON SCHEMA public TO tourquery_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO tourquery_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO tourquery_readonly;
ALTER ROLE tourquery_readonly SET statement_timeout = '5s';

-- Conversation memory user (Step 9). LangGraph's checkpoint tables are created
-- in agent_memory by scripts/setup_memory.py, connected as this user.
CREATE ROLE tourquery_memory WITH LOGIN PASSWORD :'memory_password';
CREATE SCHEMA agent_memory;
GRANT USAGE, CREATE ON SCHEMA agent_memory TO tourquery_memory;
REVOKE ALL ON SCHEMA public FROM tourquery_memory;
ALTER ROLE tourquery_memory SET search_path = agent_memory;
