# TourQuery — Natural Language to SQL Agent for ATP Tennis Data

> See [PROGRESS.md](PROGRESS.md) for current build status and [ELEVATION.md](ELEVATION.md)
> for the 9-10 upgrade backlog. If resuming after a session reset, read
> `.claude/skills/tourquery-context/SKILL.md` first.

## What this is

A production-shaped GenAI agent that lets a user ask questions in plain English
about real ATP tennis data (players, matches, tournaments, rankings) and get
answers grounded in a real relational database — not a toy demo against a
3-table sample dataset, but a system that handles a realistic schema safely,
explains itself, corrects its own mistakes, and is measured rather than
eyeballed.

This is the first dedicated GenAI project on the resume, meant to back up
LangChain/LangGraph/RAG/VectorDB skills already claimed but not yet backed by
a real, deployed system.

## Real use case

People want to ask sports-stats questions in plain English ("what's the
head-to-head between Alcaraz and Sinner?") instead of writing SQL or digging
through a stats site. A safe NL→SQL agent over real match/player/ranking data
is a real, demonstrable product category. Building one end-to-end — including
the parts tutorials skip: guardrails, schema retrieval at scale,
self-correction, evaluation, and cost/latency measurement — is what turns
this from "I called an LLM API" into "I built an agentic system I can defend
in an interview."

Because the underlying data is real (not synthetic), answers are also
independently verifiable — a recruiter or interviewer can fact-check "who
has the better 2024 head-to-head, Djokovic or Alcaraz" against reality, which
is a stronger demo than a system where nothing can be cross-checked.

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
- **DevOps** — CI/CD (GitHub Actions), live deployment (Railway/Fly.io + Vercel)
- **Performance engineering** (the differentiator vs. typical GenAI portfolio projects) — load testing, p50/p95 latency measurement, token-cost accounting, semantic caching hit-rate

## Domain, schema, and vector DB decisions

**Domain: real ATP tour data (2023-2025), no synthetic sports theme.**
Sourced from Jeff Sackmann's public ATP datasets (original repo taken down;
loaded via a community archival mirror — see PROGRESS.md decision table).
Real, messy, independently verifiable data beats a self-generated dataset
for demo credibility.

**Schema (7 populated tables + 2 empty/unused)**: `players`, `venues`,
`tournaments`, `matches`, `sets`, `rankings_history`, `injuries` (synthetic —
see below) hold real or synthetic data. `rallies` and `shots` exist in the
schema (originally designed for shot-level detail) but are deliberately left
**empty** — no public data source exists for shot-level tracking on regular
tour matches, and generating that volume synthetically wasn't worth the
storage/complexity for a portfolio demo. Kept in the schema rather than
dropped so schema-introspection/retrieval logic has to correctly recognize
"this table exists but has no rows" rather than assuming every table in the
schema is populated — a realistic condition in real production databases.

The `injuries` table is fully synthetic (no public injury dataset exists)
and deliberately uses `player_ref` instead of `player_id` — a
legacy-migration-style naming inconsistency that forces the agent to
actually read column names from introspection rather than pattern-match from
other tables.

**Question categories** (drive both the agent's prompting and the eval set) —
see PROGRESS.md for the concrete example-question bank:
1. Simple lookup — "How many matches did Carlos Alcaraz play in 2024?"
2. Aggregation — "What's Djokovic's win rate on clay from 2023-2025?"
3. Join-heavy / head-to-head — "What's the head-to-head between Alcaraz and Sinner?"
4. Time-series — "Show Jannik Sinner's ranking trend over 2024"
5. Ranking / top-N — "Top 5 players by match wins in 2024"
6. Ambiguous (tests clarification behavior) — "Who's the best server?" (no serve-stat column exists — agent should clarify or explain what it can answer)
7. Multi-turn follow-up (tests checkpointed memory) — "Now just the ones he lost" / "now only on hard courts"
8. Derived business logic — "Which players went undefeated in any tournament they entered in 2024?" / "how did ranking change after injury?" (no direct column — must be computed)
9. Guardrail probe — "Update Djokovic's ranking to 1" → must be refused, never executed
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

- A Google Gemini API key (free tier) as the primary LLM provider; Anthropic/OpenAI kept optional as fallbacks (provider-agnostic via `init_chat_model`)
- Python 3.11+, `uv` for dependency management
- `sqlglot` for SQL static analysis/validation
- `psycopg` for DB access
- LangSmith account (free tier) for tracing
- Node.js + Next.js for the frontend
- Accounts for deployment: Railway or Fly.io (API), Vercel (frontend) — free tiers are enough (DB is already on Neon)
- A gold evaluation set we write ourselves (20-40 question/SQL pairs) once the agent works, drawn from the example-question bank in PROGRESS.md
- GitHub repo with Actions enabled for CI

## Build order

0. **Project skeleton** — folder layout, `uv`, pydantic-settings config, `.env` — done
1. **Postgres (Neon, cloud-hosted) + real seed data** — no Docker (no admin rights on this machine blocks WSL/Docker Desktop and native Postgres). Real ATP match/player/tournament/ranking data (2023-2025) loaded from Sackmann's public dataset; `sets` parsed from real score strings; `injuries` synthetic (Faker) with the `player_ref` naming trap; `rallies`/`shots` left empty (no data source, not worth fabricating) — done
2. **Read-only DB role + connection layer** — a dedicated Postgres role with SELECT-only grants; connection pooling
3. **Schema introspection module** — pulls live schema (tables, columns, types, FKs, sample values) at runtime, cached — never hardcoded
4. **Schema retrieval (RAG over the schema)** — embed table/column descriptions into pgvector, retrieve top-k relevant tables per incoming question instead of dumping the whole schema into the prompt
5. **SQL generation node** — structured output / tool calling, few-shot examples, Postgres-dialect aware
6. **SQL guardrails/validator** — sqlglot-based static analysis: SELECT-only, no DDL/DML, forced LIMIT, table/column existence check, blocked functions/schemas
7. **Execution + self-correction loop (LangGraph)** — run the validated query; on a DB error, feed the error back to the LLM for a bounded number of retries
8. **Answer synthesis node** — natural-language answer plus the SQL used plus the result table, always shown together
9. **Conversation memory** — LangGraph Postgres-backed checkpointer for multi-turn follow-ups ("now filter to hard courts only")
10. **Observability** — LangSmith tracing, structured logs, per-request latency/token/cost tracking
11. **Evaluation harness** — gold question/SQL dataset, execution-accuracy metric + LLM-as-judge for answer quality, runnable as a script
12. **FastAPI service** — streaming `/chat` endpoint, session management, error handling, basic rate limiting, API-key auth
13. **Chat frontend (Next.js/React)** — chat panel + collapsible SQL/result panel per response
14. **Guardrail hardening** — prompt-injection test cases, PII-column masking option, circuit breakers on retry count and query cost
15. **CI/CD** — GitHub Actions running the guardrail tests and eval suite on every push, failing the build on regression
16. **Full containerization** — Dockerfiles for API and frontend
17. **Live deployment** — API on Railway/Fly.io, frontend on Vercel, public demo link (DB already on Neon)
18. **Load & cost benchmarking** — concurrent load test (locust or async script), report p50/p95 latency and token cost per query, add semantic caching and report the resulting hit-rate/latency improvement
19. **README polish** — architecture diagram, threat-model table, demo GIF, live link, eval/CI badges

## Next step

Step 0 and Step 1 are done. Next: Step 2 (read-only DB role + connection layer).
