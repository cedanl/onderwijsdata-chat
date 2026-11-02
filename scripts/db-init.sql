-- PostgreSQL: de applicatiegebruiker en de database voor onderwijsdata-chat, op een zelf beheerde server.
-- Op SURF SDP levert het platform beide; dit script is daar niet nodig (docs/deployment.md).
--
-- De tabellen maakt de app zelf bij de start (persistence/db.py, init_db); dit script maakt er geen (#825).
-- Draai het als superuser, met het wachtwoord als psql-variabele, niet in het bestand:
--
--   psql -U postgres -v wachtwoord='<sterk wachtwoord>' -f scripts/db-init.sql

\set ON_ERROR_STOP on

\if :{?wachtwoord}
\else
  \echo 'Geef het wachtwoord mee: psql -v wachtwoord=... -f scripts/db-init.sql'
  \quit
\endif

-- De applicatiegebruiker, als die nog niet bestaat
SELECT format('CREATE ROLE onderwijsdata_chat LOGIN PASSWORD %L', :'wachtwoord')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'onderwijsdata_chat')
\gexec

-- De database, als die nog niet bestaat
SELECT 'CREATE DATABASE onderwijsdata_chat OWNER onderwijsdata_chat'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'onderwijsdata_chat')
\gexec

GRANT CREATE ON DATABASE onderwijsdata_chat TO onderwijsdata_chat;

-- Het schema public van de gebruiker, zodat de app er haar tabellen in kan maken (PostgreSQL 15+)
\c onderwijsdata_chat
ALTER SCHEMA public OWNER TO onderwijsdata_chat;
