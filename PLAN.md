# RallyQuery — Natural Language to SQL Agent for Sports Analytics

> See [PROGRESS.md](PROGRESS.md) for current build status and [ELEVATION.md](ELEVATION.md)
> for the 9-10 upgrade backlog. If resuming after a session reset, read
> `.claude/skills/rallyquery-context/SKILL.md` first.

## What this is

A production-shaped GenAI agent that lets a user ask questions in plain English
and get answers grounded in a real relational database — not a toy demo against
a 3-table sample dataset, but a system that handles a realistic schema safely,
explains itself, corrects its own mistakes, and is measured rather than
eyeballed.

This is the first dedicated GenAI project on the resume. Past experience is
CV/real-time-systems in sports analytics (Stupa Sports: ball tracking,
rally/shot state machines, stroke classification; Future Sportler:
biomechanics + VLM coaching) plus one GenAI bullet at NHA (few-shot
prompting + RAG + eval scoring gates). The skills section already claims
LangChain, LangGraph, RAG, and VectorDBs — this project is what backs that
claim with a real, deployed system, and the domain choice ties it directly
back to the sports-analytics work already on the resume.

## Real use case

Sports analytics pipelines (like the ball-tracking, rally, and shot-detection
systems already built at Stupa) produce rich structured data — but coaches,
analysts, and scouts don't write SQL. They need to ask "who's our best server
on clay this season?" and get an answer, not a data-team ticket. A safe
NL→SQL agent over match/player/shot data is a real product category (sports
analytics vendors sell exactly this). Building one end-to-end — including the
parts tutorials skip: guardrails, schema retrieval at scale, self-correction,
evaluation, and cost/latency measurement — is what turns this from "I called
an LLM API" into "I built an agentic system I can defend in an interview,"
and it's a direct extension of the analytics work already on the resume
rather than an unrelated side project.

## Skills this project demonstrates

- **LangChain** — LCEL runnables, structured output, prompt composition, tool calling
- **LangGraph** — StateGraph with conditional edges, retry/self-correction loop, checkpointing for multi-turn memory, human-in-the-loop potential
- **RAG applied to schema, not just documents** — embedding table/column descriptions and retrieving relevant tables per question instead of dumping the full schema into the prompt
- **Vector DBs** — pgvector (reusing the same Postgres instance) for schema-chunk embeddings
- **Prompt engineering** — few-shot SQL examples, dialect-aware generation, output parsing
- **SQL / DBMS** — schema design, read-only roles, query plans, indexing, transaction isolation for safe execution
- **Guardrails / AI safety engineering** — static SQL validation (sqlglot), allow-listing, injection defense (both SQL and prompt injection), circuit breakers on cost/retries
- **Evaluation & observability** — gold Q&A dataset, execution-accuracy metric, LLM-as-judge, LangSmith tracing, CI-gated regression testing
- **Backend engineering** — FastAPI, streaming responses, session/thread management, auth, rate limiting
- **Frontend** — a minimal Next.js/React chat client consuming a streaming API
- **DevOps** — Docker Compose (API + Postgres + frontend), CI/CD (GitHub Actions), live deployment (Railway/Fly.io + Vercel)
- **Performance engineering** (the differentiator vs. typical GenAI portfolio projects) — load testing, p50/p95 latency measurement, token-cost accounting, semantic caching hit-rate — the same measurement discipline as the real-time CV work, applied to an LLM system

## Domain, schema, and vector DB decisions

**Domain: sports performance analytics.** Chosen deliberately over a generic
e-commerce dataset because it ties directly to the real professional
experience already on the resume (Stupa Sports: ball tracking, rally/shot
state machines, stroke classification; Future Sportler: biomechanics +
coaching). This is framed as "the kind of match/rally data a CV pipeline
like the ones already built would produce, now queryable in plain English"
— a coherent story rather than an unrelated side project.

**Schema (13 tables)**: `players`, `teams`, `coaches`, `venues`,
`tournaments`, `matches`, `sets`, `rallies`, `shots` (shot_type, speed_kmh,
spin_type, is_winner/is_error — mirrors real ball-tracking/stroke
classification output), `rankings_history` (time-series), `sponsorships`,
`officials`, `injuries`. The `injuries` table deliberately uses `player_ref`
instead of `player_id` — a legacy-migration-style naming inconsistency that
forces the agent to actually read column names from introspection rather
than pattern-match from other tables. This size is also the reason
schema-retrieval RAG earns its place: small enough to build quickly, large
enough that stuffing the full schema into every prompt would be wasteful.

**Question categories** (drive both the agent's prompting and the eval set):
1. Simple lookup — "How many players are from India?"
2. Aggregation — "Average rally length at the 2025 Grand Slam?"
3. Join-heavy — "Which player has the highest win rate against left-handed opponents?"
4. Time-series — "Show player X's ranking trend over the last 12 months"
5. Ranking — "Top 5 players by winners hit this season"
6. Ambiguous (tests clarification behavior) — "Who's the best server?" (aces? speed? serve-point win rate?)
7. Multi-turn follow-up (tests checkpointed memory) — "Now filter that to clay-court matches only"
8. Derived business logic — "Which players are undefeated this season?" / "win rate after returning from injury" (no direct column — must be computed)
9. Guardrail probe — "Update player X's ranking to 1" → must be refused, never executed
10. Naming-trap probe — a question touching `injuries` to confirm the agent resolves `player_ref` correctly instead of hallucinating `player_id`

**Vector DB: pgvector**, inside the same Postgres instance that holds the
operational data — not a separate Qdrant/Chroma/Pinecone service. Fewer
moving parts to run and back up, and "Postgres as both system of record and
vector store" is a real, defensible production pattern rather than a
shortcut. The retrieval layer will sit behind a small interface so it reads
as a deliberate choice (swappable later) rather than a skill gap.

## What "good" looks like when this is done

- A live URL a recruiter can open and actually use, not just a GitHub repo
- Every answer shows its generated SQL and the result table — no black box
- The agent refuses/corrects instead of silently returning wrong data on ambiguous or malformed queries
- A README with a threat-model table (SQL injection / prompt injection / runaway cost — and how each is blocked)
- A CI badge showing an eval suite passing on every commit
- A short benchmark section: latency percentiles and cost per query under load

## What we need before/while building

- Docker (for Postgres + pgvector locally, and for packaging the API)
- An Anthropic and/or OpenAI API key (provider-agnostic via `init_chat_model`)
- Python 3.11+, `uv` (or poetry) for dependency management
- `sqlglot` for SQL static analysis/validation
- `psycopg` / SQLAlchemy for DB access
- LangSmith account (free tier) for tracing
- Faker (or similar) to generate realistic seed data
- Node.js + Next.js for the frontend
- Accounts for deployment: Railway or Fly.io (API + Postgres), Vercel (frontend) — free tiers are enough
- A gold evaluation set we write ourselves (20-40 question/SQL pairs) once the schema is finalized
- GitHub repo with Actions enabled for CI

## Build order

0. **Project skeleton** — folder layout, `uv`/poetry, pydantic-settings config, `.env.example`
1. **Dockerized Postgres + realistic seed data** — docker-compose, Faker-based generator for the 13-table sports analytics schema (players, matches, rallies, shots, rankings, etc.) with FKs, nullable columns, and the `player_ref` naming inconsistency (so it isn't a clean toy schema)
2. **Read-only DB role + connection layer** — a dedicated Postgres role with SELECT-only grants; SQLAlchemy connection pooling
3. **Schema introspection module** — pulls live schema (tables, columns, types, FKs, sample values) at runtime, cached — never hardcoded
4. **Schema retrieval (RAG over the schema)** — embed table/column descriptions into pgvector, retrieve top-k relevant tables per incoming question instead of dumping the whole schema into the prompt
5. **SQL generation node** — structured output / tool calling, few-shot examples, Postgres-dialect aware
6. **SQL guardrails/validator** — sqlglot-based static analysis: SELECT-only, no DDL/DML, forced LIMIT, table/column existence check, blocked functions/schemas
7. **Execution + self-correction loop (LangGraph)** — run the validated query; on a DB error, feed the error back to the LLM for a bounded number of retries
8. **Answer synthesis node** — natural-language answer plus the SQL used plus the result table, always shown together
9. **Conversation memory** — LangGraph Postgres-backed checkpointer for multi-turn follow-ups ("now filter to last month")
10. **Observability** — LangSmith tracing, structured logs, per-request latency/token/cost tracking
11. **Evaluation harness** — gold question/SQL dataset, execution-accuracy metric + LLM-as-judge for answer quality, runnable as a script
12. **FastAPI service** — streaming `/chat` endpoint, session management, error handling, basic rate limiting, API-key auth
13. **Chat frontend (Next.js/React)** — chat panel + collapsible SQL/result panel per response
14. **Guardrail hardening** — prompt-injection test cases, PII-column masking option, circuit breakers on retry count and query cost
15. **CI/CD** — GitHub Actions running the guardrail tests and eval suite on every push, failing the build on regression
16. **Full containerization** — Dockerfiles for API and frontend, one-command `docker-compose up` for the whole stack
17. **Live deployment** — API + Postgres on Railway/Fly.io, frontend on Vercel, public demo link
18. **Load & cost benchmarking** — concurrent load test (locust or async script), report p50/p95 latency and token cost per query, add semantic caching and report the resulting hit-rate/latency improvement
19. **README polish** — architecture diagram, threat-model table, demo GIF, live link, eval/CI badges

## Next step

Start with Step 0 (project skeleton) and Step 1 (Dockerized Postgres + seed data).
