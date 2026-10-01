-- Part 1: core reference tables

CREATE TABLE venues (
    venue_id    SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    city        TEXT NOT NULL,
    country     TEXT NOT NULL,
    surface     TEXT NOT NULL CHECK (surface IN ('clay', 'hard', 'grass', 'indoor'))
);

CREATE TABLE players (
    player_id     INTEGER PRIMARY KEY,
    first_name    TEXT NOT NULL,
    last_name     TEXT NOT NULL,
    nationality   TEXT NOT NULL,
    date_of_birth DATE,
    plays         TEXT CHECK (plays IN ('left', 'right'))
);

-- Part 2: tournament / match / rally / shot hierarchy

CREATE TABLE tournaments (
    tournament_id SERIAL PRIMARY KEY,
    name          TEXT NOT NULL,
    year          INTEGER NOT NULL,
    venue_id      INTEGER REFERENCES venues(venue_id),
    surface       TEXT NOT NULL CHECK (surface IN ('clay', 'hard', 'grass', 'indoor')),
    start_date    DATE NOT NULL,
    end_date      DATE NOT NULL
);

CREATE TABLE matches (
    match_id       SERIAL PRIMARY KEY,
    tournament_id  INTEGER NOT NULL REFERENCES tournaments(tournament_id),
    player1_id     INTEGER NOT NULL REFERENCES players(player_id),
    player2_id     INTEGER NOT NULL REFERENCES players(player_id),
    winner_id      INTEGER REFERENCES players(player_id),
    match_date     DATE NOT NULL,
    round          TEXT NOT NULL
);

CREATE TABLE sets (
    set_id         SERIAL PRIMARY KEY,
    match_id       INTEGER NOT NULL REFERENCES matches(match_id),
    set_number     INTEGER NOT NULL,
    player1_games  INTEGER NOT NULL,
    player2_games  INTEGER NOT NULL
);

CREATE TABLE rallies (
    rally_id       SERIAL PRIMARY KEY,
    set_id         INTEGER NOT NULL REFERENCES sets(set_id),
    rally_number   INTEGER NOT NULL,
    shot_count     INTEGER NOT NULL,
    winner_id      INTEGER REFERENCES players(player_id),
    duration_sec   NUMERIC(5,2)
);

CREATE TABLE shots (
    shot_id        SERIAL PRIMARY KEY,
    rally_id       INTEGER NOT NULL REFERENCES rallies(rally_id),
    shot_number    INTEGER NOT NULL,
    player_id      INTEGER NOT NULL REFERENCES players(player_id),
    shot_type      TEXT NOT NULL CHECK (shot_type IN ('serve', 'forehand', 'backhand', 'volley', 'smash', 'lob', 'drop_shot')),
    speed_kmh      NUMERIC(5,2),
    spin_type      TEXT CHECK (spin_type IN ('topspin', 'slice', 'flat', 'kick')),
    is_winner      BOOLEAN NOT NULL DEFAULT FALSE,
    is_error       BOOLEAN NOT NULL DEFAULT FALSE
);

-- Part 3: peripheral tables

CREATE TABLE rankings_history (
    ranking_id     SERIAL PRIMARY KEY,
    player_id      INTEGER NOT NULL REFERENCES players(player_id),
    ranking_date   DATE NOT NULL,
    rank           INTEGER NOT NULL,
    points         INTEGER
);

-- Deliberate legacy-naming trap: player_ref instead of player_id,
-- forcing the agent to read column names via introspection rather
-- than pattern-match from other tables.
CREATE TABLE injuries (
    injury_id      SERIAL PRIMARY KEY,
    player_ref     INTEGER NOT NULL REFERENCES players(player_id),
    injury_type    TEXT NOT NULL,
    start_date     DATE NOT NULL,
    end_date       DATE,
    matches_missed INTEGER DEFAULT 0
);

-- Part 4: schema-retrieval RAG (Step 4). One row per table, storing an
-- embedding of that table's introspected description (see
-- src/tourquery/introspection.py render_schema/get_schema) so a question
-- only needs to retrieve the top-k relevant tables instead of every table's
-- schema being stuffed into every prompt.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE schema_embeddings (
    table_name TEXT PRIMARY KEY,
    chunk_text TEXT NOT NULL,
    embedding  vector(768) NOT NULL
);

-- One-sentence purpose descriptions, read live via pg_catalog by
-- introspection.get_table_comments() and folded into each table's embedded
-- chunk_text. Added after discovering that a pure column-list description
-- retrieved poorly for player-centric questions (e.g. "Djokovic's win rate
-- on clay" missed the players table entirely) -- these give the embedding
-- model actual semantic content about what each table is *for*, not just
-- what columns it has.
COMMENT ON TABLE players IS 'Individual tennis players: name, nationality, and playing hand.';
COMMENT ON TABLE venues IS 'Physical locations where tournaments are played, including court surface.';
COMMENT ON TABLE tournaments IS 'ATP tournaments/events, each tied to a venue, surface, and date range.';
COMMENT ON TABLE matches IS 'Individual tennis matches between two players within a tournament, including who won.';
COMMENT ON TABLE sets IS 'Set-by-set game scores within a match.';
COMMENT ON TABLE rallies IS 'Point-by-point rally data within a set. Currently empty: no public data source exists.';
COMMENT ON TABLE shots IS 'Individual shot data (type, speed, spin) within a rally. Currently empty: no public data source exists.';
COMMENT ON TABLE rankings_history IS 'Weekly ATP ranking snapshots for each player over time.';
COMMENT ON TABLE injuries IS 'Player injury records: type, dates, matches missed. Synthetic data, currently empty.';
