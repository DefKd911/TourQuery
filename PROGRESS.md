# RallyQuery — Progress Log

This file is the single source of truth for "where are we right now." Update
it at the end of every work session — before status, after status, and what
changed. If a chat session resets, read this file first, then `PLAN.md` and
`ELEVATION.md`, before doing anything else.

## Current status

**Phase**: Planning complete. No code written yet.
**Next action**: Step 0 (project skeleton) + Step 1 (Dockerized Postgres + seed data).

## Decisions locked in so far

| Decision | Choice | Why |
|---|---|---|
| Project name | RallyQuery | Ties to sports/rally domain, reads as a real product name |
| Domain | Sports performance analytics (players, matches, rallies, shots, rankings) | Connects to real Stupa Sports / Future Sportler experience on resume |
| Database | Postgres (Docker) | Realistic, supports pgvector, matches "SQL" skill on resume |
| Vector DB | pgvector (same Postgres instance) | Fewer moving parts; defensible production pattern vs. adding a separate vector service |
| LLM provider | Provider-agnostic via `init_chat_model` (Anthropic + OpenAI) | Showcases engineering flexibility |
| Frontend | Next.js/React minimal chat UI | Reads as a real product, not a notebook demo |
| Deliverable depth | Full showcase (guardrails, eval, observability, CI, live deployment, benchmarking) | User has 1 YOE and needs project depth to back up claimed GenAI skills |
| Deployment target | Railway or Fly.io (API+DB) + Vercel (frontend) | Free tier, live demo link matters more than a clone-and-run repo |
| Legacy-naming trap | `injuries.player_ref` instead of `player_id` | Forces agent to read schema instead of pattern-matching column names |

See `PLAN.md` for the full schema (13 tables), question categories, and the
step-by-step build order (steps 0-19).

## Step-by-step log

Update this table as each step starts/completes. Status values: `not started`,
`in progress`, `done`, `blocked`.

| Step | Description | Status | Notes |
|---|---|---|---|
| 0 | Project skeleton | not started | |
| 1 | Dockerized Postgres + seed data | not started | |
| 2 | Read-only DB role + connection layer | not started | |
| 3 | Schema introspection module | not started | |
| 4 | Schema retrieval (RAG over schema, pgvector) | not started | |
| 5 | SQL generation node | not started | |
| 6 | SQL guardrails/validator (sqlglot) | not started | |
| 7 | Execution + self-correction loop (LangGraph) | not started | |
| 8 | Answer synthesis node | not started | |
| 9 | Conversation memory (checkpointer) | not started | |
| 10 | Observability (LangSmith, logs) | not started | |
| 11 | Evaluation harness | not started | |
| 12 | FastAPI service | not started | |
| 13 | Chat frontend | not started | |
| 14 | Guardrail hardening | not started | |
| 15 | CI/CD | not started | |
| 16 | Full containerization | not started | |
| 17 | Live deployment | not started | |
| 18 | Load & cost benchmarking | not started | |
| 19 | README polish | not started | |

## Open questions / things to revisit

- None yet.

## Session history

- **2026-09-20**: Planning session. Defined domain (sports analytics), schema,
  question categories, vector DB choice (pgvector), and full 20-step build
  order. Renamed project ChatSQL → RallyQuery. Created PLAN.md, PROGRESS.md,
  ELEVATION.md, and the `.claude/skills/rallyquery-context` persistence skill.
  No code written yet.
