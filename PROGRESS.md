# TourQuery — Progress Log

This file is the single source of truth for "where are we right now." Update
it at the end of every work session — before status, after status, and what
changed. If a chat session resets, read this file first, then `PLAN.md` and
`ELEVATION.md`, before doing anything else.

## Current status

**Phase**: Live at https://tourquery.onrender.com (steps 13, 16, 17 done). Step 11 (eval) still deferred.
**Next action**: Decide on the Gemini quota (billing vs. free), then eval set -> README -> CI.

## Decisions locked in so far

| Decision | Choice | Why |
|---|---|---|
| Project name | TourQuery (renamed from ChatSQL → RallyQuery → TourQuery) | RallyQuery's rally/shot-tracking narrative no longer fits once we dropped synthetic rally/shot data in favor of real ATP data; TourQuery reflects "ATP Tour" + query |
| Domain | Real ATP tour data (players, matches, tournaments, rankings), 2023-2025 | No CV-pipeline/sports-tracking narrative — this is a standalone NL→SQL project over a real, verifiable, publicly-sourced dataset |
| Database | Postgres via Neon (cloud, free tier) | No admin rights on machine — WSL and native Postgres installer both blocked; Neon needs no install and has pgvector built in |
| Seed data | Real ATP data (Sackmann public dataset, via community archival mirror since the original repo was taken down) for players/matches/tournaments/sets/rankings, 2023-2025, ATP only; Faker-synthetic only for `injuries` | Real data is messier and more verifiable than synthetic; no public source exists for injuries so that stays synthetic |
| Rallies/shots | Left in the schema but intentionally empty — no synthetic generation | No public shot-level data exists for regular tour matches, and generating it synthetically wasn't worth the volume/complexity for a demo once the CV-pipeline narrative was dropped. Kept as empty tables so schema-introspection logic has to handle "table exists, zero rows" correctly |
| Schema size | 9 tables total: 7 populated (`players`, `venues`, `tournaments`, `matches`, `sets`, `rankings_history`, `injuries`) + 2 empty (`rallies`, `shots`) | Trimmed from an original 13-table design; dropped `teams`, `coaches`, `sponsorships`, `officials` (no real data source, individual-sport data doesn't fit "teams") |
| Vector DB | pgvector (same Postgres instance) | Fewer moving parts; defensible production pattern vs. adding a separate vector service |
| LLM provider | Google Gemini (free tier) primary, Anthropic/OpenAI optional fallback, via `init_chat_model` | Free tier keeps cost at zero during development; still provider-agnostic |
| Frontend | Next.js/React minimal chat UI | Reads as a real product, not a notebook demo |
| Deliverable depth | Full showcase (guardrails, eval, observability, CI, live deployment, benchmarking) | User has 1 YOE and needs project depth to back up claimed GenAI skills |
| Deployment target | Railway or Fly.io (API) + Vercel (frontend) | Free tier; DB is already on Neon |
| Legacy-naming trap | `injuries.player_ref` instead of `player_id` | Forces agent to read schema instead of pattern-matching column names |
| Dependency manager | `uv` | Fast, modern |

See `PLAN.md` for the full schema, question categories, and the step-by-step
build order (steps 0-19).

## Example questions the finished agent should handle

Locked in as the basis for the eval set (Step 11) and demo script. Grounded
in what's actually in the DB — verified these players/scenarios exist in the
loaded data (Djokovic, Alcaraz, Sinner, Nadal, Medvedev, Fritz all present).

- **Simple lookup**: "How many matches did Carlos Alcaraz play in 2024?"
- **Aggregation**: "What's Djokovic's win rate on clay between 2023 and 2025?"
- **Join-heavy / head-to-head**: "What's the head-to-head record between Alcaraz and Sinner?"
- **Ranking / top-N**: "Who are the top 5 players by number of match wins in 2024?"
- **Time-series**: "Show Jannik Sinner's ranking trend over 2024."
- **Ambiguous** (tests clarification behavior): "Who's the best server?" — no serve-stat column exists; agent should clarify or explain what it can answer instead of guessing
- **Multi-turn follow-up**: "Show me Medvedev's matches in 2024." → "Now just the ones he lost." → "Now only on hard courts."
- **Derived/business logic**: "Which players went undefeated in any tournament they entered in 2024?" / "Which players missed matches due to injury and how did their ranking change afterward?"
- **Guardrail probes**: "Delete all of Nadal's matches." / "Update Djokovic's ranking to 1." → must be refused, never executed
- **Naming-trap probe**: "Which players have had an injury lasting more than 30 days?" (tests correct resolution of `injuries.player_ref`)

## Step-by-step log

Update this table as each step starts/completes. Status values: `not started`,
`in progress`, `done`, `blocked`.

| Step | Description | Status | Notes |
|---|---|---|---|
| 0 | Project skeleton | done | `uv init --package`, src/tourquery layout, `.gitignore`, `.env`, `pydantic-settings` config module (Gemini as required key, Anthropic/OpenAI optional) |
| 1 | Postgres (Neon) + real seed data | done | Schema (9 tables) created via `sql/schema.sql`; real ATP data loaded via `scripts/seed_db.py` — 684 players, 310 venues, 430 tournaments, 8,953 matches, 23,032 sets, 71,816 ranking snapshots. `rallies`/`shots` intentionally left empty. Synthetic `injuries` data still pending. |
| 2 | Read-only DB role + connection layer | done | Created `tourquery_readonly` Postgres role on Neon (SELECT-only grants on all tables + default privileges for future tables), verified DELETE is blocked at the DB level. `config.py` now has `readonly_database_url` alongside owner `database_url`. `src/tourquery/db.py` wraps it in a pooled SQLAlchemy Core engine (`postgresql+psycopg://` dialect) — this is what Step 7's execution loop will use. |
| 3 | Schema introspection module | done | `src/tourquery/introspection.py`: columns+types (`information_schema.columns`), FKs, sample values for text columns, row counts, and a `render_schema()` prompt-formatter. Found and fixed a real bug: `information_schema.table_constraints` hides FK metadata from a SELECT-only role (needs pg_catalog instead) — verified `injuries.player_ref -> players.player_id` resolves correctly through the readonly connection. |
| 4 | Schema retrieval (RAG over schema, pgvector) | done | `schema_embeddings` table (pgvector, 768-dim, `gemini-embedding-001`) holds one embedded chunk per real table, built via `scripts/embed_schema.py`. Added `COMMENT ON TABLE` purpose descriptions (read live via pg_catalog, not hardcoded) after discovering pure column-list chunks retrieved poorly for player-centric questions. `src/tourquery/retrieval.py`: top-k semantic search (`<=>` cosine distance) + one-directional FK-graph expansion (forward only — backward expansion exploded through the `players` hub table, pulling in all 9 tables every time). Verified against real questions: correctly excludes irrelevant tables (e.g. head-to-head correctly drops rallies/shots/injuries/sets) while still surfacing `players` every time. Also excluded `schema_embeddings` itself from introspection (`EXCLUDED_TABLES`) after it briefly got embedded as if it were a 10th domain table. |
| 5 | SQL generation node | done | `src/tourquery/sql_generation.py`: `ChatGoogleGenerativeAI` (`gemini-2.5-flash`, pinned after checking the full available-models list to avoid preview/exotic ones) + LangChain structured output (`GeneratedSQL` Pydantic model: sql + explanation) + a system prompt wired to Step 4's `get_relevant_tables()` output. Verified against real questions: both generated queries executed successfully against Neon (Alcaraz 67 matches in 2024; Alcaraz-Sinner head-to-head 8-4 in the dataset window). A guardrail-probe question ("update Djokovic's ranking to 1") was correctly refused at the prompt level -- but that's compliance, not enforcement; Step 6 (sqlglot static validation) is the real enforcement layer, on top of Step 2's read-only DB role. |
| 6 | SQL guardrails/validator (sqlglot) | done | Two layers. (1) `ALTER ROLE tourquery_readonly SET statement_timeout = '5s'` -- verified a `pg_sleep(7)` gets cancelled. (2) `src/tourquery/guardrails.py` `validate_sql()`: exactly one statement, must be SELECT/UNION, rejects any write/DDL/`SELECT INTO`/`FOR UPDATE` anywhere in the tree, only allows real domain tables (blocks `pg_catalog`, `schema_embeddings`), blocks all `pg_*` functions plus `dblink`/`set_config`/`current_setting`/etc., checks every column exists via `sqlglot.optimizer.qualify` (catches the `injuries.player_id` naming trap), adds `LIMIT 1000` if missing and clamps larger limits. 22 pytest cases in `tests/test_guardrails.py` (fake schema, no DB needed -- CI-ready). Verified on real LLM output: 4 example questions all passed and executed correctly. |
| 7 | Execution + self-correction loop (LangGraph) | done | `src/tourquery/graph.py`: StateGraph `retrieve -> generate -> validate -> execute`, with conditional edges sending validator errors and retryable DB errors (ProgrammingError, DataError, statement timeout) back to `generate` with the failed SQL + error message, max 3 attempts. LLM/API errors (e.g. rate limits) end cleanly with `status=failed` and are not retried. `generate_sql` now takes `previous_sql`/`error` feedback. Tested both loop paths by forcing a bad first query: validator caught `injuries.player_id` and the model fixed it to `player_ref`; then a DB type error (`integer > interval`) was routed back, which revealed the model didn't know Postgres `date - date` returns an integer -- fixed with a "Postgres notes" section in the system prompt, after which the question succeeds first try. |
| 8 | Answer synthesis node | done | `src/tourquery/answer_synthesis.py` + `synthesize`/`refuse`/`fail` nodes in `graph.py`. Every run ends with `status` ok / refused / failed and an `answer`, alongside `safe_sql`, `columns`, `rows`. Summary uses `gemini-3.5-flash-lite` (separate per-model free quota from the SQL model; `gemini-2.5-flash-lite` is unavailable to new accounts) and is told to use only numbers in the result rows. Added a `refusal` field to `GeneratedSQL`: write requests ("Delete all of Nadal's matches") now end `status=refused` with no SQL run, instead of being silently rewritten into a SELECT. If the summary call fails, the results are still returned with fallback text and a logged warning. Verified: top-5 wins summary (handles the tie), empty-result case, head-to-head end to end. |
| 9 | Conversation memory (checkpointer) | done | LangGraph `PostgresSaver` (`src/tourquery/memory.py`), state saved per `thread_id`. Runs as a third DB user `tourquery_memory` that can only write to its own `agent_memory` schema (verified: `permission denied` on `players`), so the agent's query user stays read-only and the checkpoint tables never appear in the agent's schema view. Roles documented in `sql/roles.sql`; checkpoint tables created by `scripts/setup_memory.py`. `graph.py` reorganized for readability: `history` list grows one `Turn` (self-contained question, SQL, tables, answer) per question via a reducer; per-question fields reset in `retrieve`; last 3 turns (question + SQL, not rows) go to the SQL model; follow-ups carry the previous turn's tables into retrieval; the SQL model also returns `standalone_question` in the same call (no extra LLM call). `ask(question, thread_id)`. Verified, each turn in a fresh process: Medvedev 2024 -> 67 matches -> "ones he lost" 21 -> "only on hard courts" 14, filters kept each time; a separate thread had no Medvedev context; a topic change on the same thread dropped the old filters. |
| 10 | Observability (LangSmith, logs) | done | Kept deliberately simple. LangSmith tracing turns on when `LANGSMITH_API_KEY` is in `.env` (`config.py` exports it, since LangChain reads env vars, not `.env`); project `tourquery` shows each step, prompt, SQL attempt and timing. Locally, `ask()` measures total time and tokens per model (LangChain's `UsageMetadataCallbackHandler`), logs one line per question, and returns `duration_ms`/`tokens`/`thread_id`. First real finding from traces: a 57s question spent 33.5s in the `gemini-2.5-flash` SQL call (likely its default "thinking") and 9.5s in retrieve -- inputs for Step 18. |
| 11 | Evaluation harness | deferred | Planned: ~12-25 gold questions (gold SQL or expected status), scored by result-row match + status check, optional LLM-as-judge. Deferred to build the API + UI first; needed before Step 15 (CI) and before any speed tuning. Limited by the 20/day free quota. |
| 12 | FastAPI service | done | Kept minimal on purpose: `src/tourquery/api.py` with `GET /health` and `POST /ask` (`{question, thread_id?}` -> `{thread_id, status, answer, sql, columns, rows, duration_ms}`), CORS for the UI (`CORS_ORIGINS`, default localhost:3000). Run: `uv run uvicorn tourquery.api:app --reload`, docs at `/docs`. Verified over HTTP, including a follow-up via `thread_id` ("top 3 by wins in 2025" -> "now only on clay"). `graph.py` gained `ask_stream()` (progress events), with `ask()` built on it, ready if the UI wants live progress later. No auth or rate limit yet -- add before a public demo, since the free LLM quota is 20/day. |
| 13 | Chat frontend | done | Single HTML file (`src/tourquery/static/index.html`) served by FastAPI at `/` -- no Node.js (not installable without admin) and no build step. Normal chat layout with light tennis touches (ball logo, court green). Sidebar of past conversations kept in browser localStorage; reopening one loads its turns from `GET /threads/{id}` (question, answer, SQL, status -- result tables aren't stored). No endpoint lists everyone's threads, by design. Greetings get a friendly `reply` via a `chat` node instead of a refusal. |
| 14 | Guardrail hardening | not started | |
| 15 | CI/CD | not started | |
| 16 | Full containerization | done | One `Dockerfile` (python:3.12-slim + uv, `uv sync --frozen --no-dev`, uvicorn on port 7860) -- API and UI are one service, so no compose file needed. |
| 17 | Live deployment | done | https://tourquery.onrender.com -- Render free web service (Docker, Ohio region next to Neon us-east-2), auto-deploys on push to github.com/DefKd911/TourQuery. Env vars: read-only + memory DB URLs, Gemini key, LangSmith key, `PORT=7860`; `DATABASE_URL` set to the read-only URL so the owner password never leaves the dev machine. Hugging Face Spaces was tried first but Docker Spaces now need PRO. Free instance sleeps after 15 min idle (~1 min wake). When the 20/day Gemini quota is used up, visitors get a friendly "demo limit reached" message. First live bug: "hi" returned 422 (3-char minimum on questions) -- fixed. |
| 18 | Load & cost benchmarking | not started | |
| 19 | README polish | not started | |

## Working mode for build steps

Each PLAN.md step is broken into small, granular substeps. Claude creates/
explains one substep at a time and pauses for the user to review and absorb
it before moving to the next — not a whole step dumped in one shot. This is
because the user wants to learn from the build, not just receive a finished
repo (see the `tourquery-learning-mode` memory).

## Open questions / things to revisit

- **LLM quota (blocking)**: Gemini free tier for `gemini-2.5-flash` is only 20 generate requests/day for this project (hit it on 2026-10-01). Not enough for retries, the Step 11 eval suite, or a public demo. Options: lighter Gemini model with a higher free limit, Groq (key already exists in the workspace `.env`), or enabling Gemini billing. Embeddings use a separate quota and were not affected.
- **LLM quota update (2026-10-01)**: switched to a different Gemini account's key as a stopgap -- same 20/day limit per model is likely, so this buys time rather than fixing it. Revisit before Step 11 (eval) and Step 17 (public demo).
- **Follow-up with no context gets guessed, not clarified**: "Now only on hard courts" on a brand-new thread was reinterpreted as "how many tournaments are on hard courts?" instead of asking "hard courts for what?". Fits ELEVATION.md item 4 (clarifying questions).
- **Summary leaks an internal detail**: answers sometimes say "the first 30 of these matches are shown" (the summary model only sees 30 rows). Tell the synthesis prompt not to mention row truncation.
- **Checkpoint storage grows**: result rows are saved in checkpoints after each step; no retention/cleanup policy yet. Needed before a public demo.
- **Answers don't mention the data window**: e.g. "Alcaraz leads the head-to-head 8-4" is correct for 2023-2025 only, but reads like a career record. Consider telling the synthesis prompt the dataset covers 2023-2025 ATP matches only, and/or add an eval case for it in Step 11.

- `injuries` table still needs synthetic (Faker) data generated — deferred when the CV-pipeline/rally-shot scope was cut; should be revisited to close out Step 1 fully.

## Session history

- **2026-09-20**: Planning session. Defined domain (sports analytics), schema,
  question categories, vector DB choice (pgvector), and full 20-step build
  order. Renamed project ChatSQL → RallyQuery. Created PLAN.md, PROGRESS.md,
  ELEVATION.md, and the `.claude/skills/rallyquery-context` persistence skill.
  No code written yet.
- **2026-09-21**: Built Step 0 (project skeleton, uv, pydantic-settings
  config). Started Step 1: blocked on Docker/WSL/native Postgres (no admin
  rights on machine) — switched to Neon cloud Postgres. Pulled ELEVATION.md
  item 2 forward: sourced real ATP match/player/tournament/ranking data
  (2023-2025) from Jeff Sackmann's public dataset (via a community archival
  mirror, since the original repo was taken down) instead of pure Faker
  generation. Built the schema (trimmed 13 → 9 tables) and an ETL pipeline
  (`scripts/seed_db.py`) that loaded it all into Neon. Decided against
  generating synthetic rally/shot data (volume/complexity not worth it for
  a demo) — this killed the CV-pipeline resume narrative that originally
  justified the project's sports/rally framing, so renamed the project
  RallyQuery → TourQuery and rewrote PLAN.md/PROGRESS.md to drop that
  narrative in favor of "safe NL→SQL agent over real, verifiable ATP data."
  Locked in a concrete example-question bank grounded in the actual loaded
  data. `injuries` synthetic data still outstanding.
- **2026-09-23**: Decided to leave `injuries` empty for now (same handling
  as `rallies`/`shots` — a deliberate empty table, not a gap). Built Step 2:
  read-only Postgres role (`tourquery_readonly`) on Neon with SELECT-only
  grants, verified DELETE is blocked at the DB level; added
  `readonly_database_url` to config and a pooled SQLAlchemy Core engine in
  `src/tourquery/db.py` for the agent's query execution (Step 7) to use.
