---
name: rallyquery-context
description: Loads full context for the RallyQuery project — a natural-language-to-SQL agent over a sports analytics database, built as the user's first dedicated GenAI portfolio project. Use whenever resuming work on RallyQuery (path Generative-AI/projects/RallyQuery) after a session reset, or any time the user references "RallyQuery" or asks to continue this project, so work picks up from the actual current state instead of re-deriving or re-deciding things already settled.
---

# RallyQuery — resume context

Read this whenever picking up work on RallyQuery in a new session. Do not
re-litigate decisions already made here — they were reached deliberately
with the user. If something seems wrong or outdated, verify against the
current files before changing it (see "Before trusting this file" below).

## What this project is

A production-shaped NL→SQL agent over a sports performance analytics
database (players, matches, rallies, shots, rankings, etc.). It's the user's
first dedicated GenAI project, meant to back up GenAI/LangChain/LangGraph/
RAG/VectorDB skills already claimed on their resume but not yet backed by
any project evidence. Full background, rationale, skills mapping, domain,
schema, and the complete step-by-step build order live in `PLAN.md` in this
same directory — read that in full before doing any planning or building.

## Read these three files, in this order, before doing anything else

1. **`PLAN.md`** — the full plan: use case, skills demonstrated, schema (13
   tables), question categories, vector DB choice, and the base 20-step
   build order (steps 0-19).
2. **`PROGRESS.md`** — the live status tracker: which step is current, what's
   done, what decisions were locked in, and a session-by-session history
   log. This is the authoritative answer to "where did we leave off."
3. **`ELEVATION.md`** — a separate backlog of upgrades (real CV-pipeline
   bridge, real public data, adversarial security testing, etc.) that would
   push the project from a strong ~8/10 portfolio piece toward genuinely
   rare 9-10 territory. These are additive and don't gate the base build —
   the user is handling overall prioritization/tiering themselves.

## User context worth knowing

- Background is CV/real-time systems (YOLOv8, TensorRT, pose estimation,
  sub-3ms real-time pipelines) at Stupa Sports Analytics and Future
  Sportler, plus one GenAI bullet at NHA (few-shot prompting, RAG, eval
  scoring gates). This is their first dedicated GenAI project.
- The sports domain choice is a deliberate narrative bridge to that
  background — but it is currently a *thematic* bridge, not a technical
  one (synthetic Faker data, no real CV pipeline feeding it), unless/until
  ELEVATION.md item 1 is pursued. Don't overstate the connection when
  discussing framing, resume bullets, or interview narrative.
- User wants full production depth: guardrails, self-correction, evaluation
  harness, observability, CI/CD, live deployment, and load/cost
  benchmarking — not just a working demo. This was an explicit choice, not
  a default — don't scope it down without asking.
- User is currently employed full-time (NHA), so building happens
  incrementally across sessions — this is exactly why this persistence
  system exists. Expect context resets between sessions to be normal, not
  exceptional.

## Working conventions for this project

- Update `PROGRESS.md` at the end of every work session: mark step
  statuses, add a dated entry to the session history log, and note any new
  decisions or open questions.
- Keep `ELEVATION.md` decisions separate from `PLAN.md`'s base step
  tracking — don't merge them into one list.
- When a plan decision changes (schema tweak, tech swap, scope change),
  update `PLAN.md` in place rather than leaving stale content, and log the
  change in `PROGRESS.md`'s decision table.

## Before trusting this file

This file and its companions are a snapshot of decisions and status as of
when they were last edited. Before acting on a specific technical claim
(e.g. "step 4 is done," "we're using library X"), verify against the actual
repo state — check whether the described files/code exist — rather than
assuming the docs are perfectly in sync with reality. If they've drifted,
fix the docs to match reality and note it in `PROGRESS.md`.
