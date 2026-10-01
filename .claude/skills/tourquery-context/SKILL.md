---
name: tourquery-context
description: Loads full context for the TourQuery project — a natural-language-to-SQL agent over real ATP tennis data, built as the user's first dedicated GenAI portfolio project. Use whenever resuming work on TourQuery (path chatSQL/TourQuery) after a session reset, or any time the user references "TourQuery" (or its earlier names ChatSQL/RallyQuery) or asks to continue this project, so work picks up from the actual current state instead of re-deriving or re-deciding things already settled.
---

# TourQuery — resume context

Read this whenever picking up work on TourQuery in a new session. Do not
re-litigate decisions already made here — they were reached deliberately
with the user. If something seems wrong or outdated, verify against the
current files before changing it (see "Before trusting this file" below).

## What this project is

A production-shaped NL→SQL agent over real ATP tennis data (players,
matches, tournaments, rankings, 2023-2025). It's the user's first dedicated
GenAI project, meant to back up GenAI/LangChain/LangGraph/RAG/VectorDB
skills already claimed on their resume but not yet backed by any project
evidence. Full background, rationale, skills mapping, domain, schema, and
the complete step-by-step build order live in `PLAN.md` in this same
directory — read that in full before doing any planning or building.

**Naming history**: ChatSQL → RallyQuery → TourQuery. It was originally
framed around a sports/rally-tracking CV-pipeline narrative (tying to the
user's CV/real-time-systems background), with synthetic Faker rally/shot
data. That was dropped on 2026-09-21 in favor of real ATP data with no
rally/shot detail and no CV-pipeline framing — see PROGRESS.md's session
history for the full reasoning. Don't reintroduce CV-pipeline language.

## Read these three files, in this order, before doing anything else

1. **`PLAN.md`** — the full plan: use case, skills demonstrated, schema,
   question categories, vector DB choice, and the base 20-step build order
   (steps 0-19).
2. **`PROGRESS.md`** — the live status tracker: which step is current, what's
   done, what decisions were locked in, the example-question bank, and a
   session-by-session history log. This is the authoritative answer to
   "where did we leave off."
3. **`ELEVATION.md`** — a separate backlog of upgrades (adversarial security
   testing, public write-up, etc.) that would push the project from a strong
   ~8/10 portfolio piece toward genuinely rare 9-10 territory. These are
   additive and don't gate the base build — the user is handling overall
   prioritization/tiering themselves.

## User context worth knowing

- Background is CV/real-time systems (YOLOv8, TensorRT, pose estimation,
  sub-3ms real-time pipelines) at Stupa Sports Analytics and Future
  Sportler, plus one GenAI bullet at NHA (few-shot prompting, RAG, eval
  scoring gates). This is their first dedicated GenAI project. **The
  project no longer ties itself to this CV background narratively** — it's
  now framed as a standalone NL→SQL project over real, verifiable data.
- User wants full production depth: guardrails, self-correction, evaluation
  harness, observability, CI/CD, live deployment, and load/cost
  benchmarking — not just a working demo. This was an explicit choice, not
  a default — don't scope it down without asking.
- User is currently employed full-time (NHA), so building happens
  incrementally across sessions — this is exactly why this persistence
  system exists. Expect context resets between sessions to be normal, not
  exceptional.
- No admin rights on the user's machine — WSL, Docker Desktop, and native
  Postgres installers are all blocked. DB runs on Neon (cloud Postgres,
  free tier) instead.
- User wants build steps taught substep-by-substep (small granular pieces,
  one at a time) rather than a whole step generated in one shot, and does
  NOT want PROGRESS.md updated after every tiny substep — batch doc updates
  after a full step or a real decision change instead.

## Working conventions for this project

- Update `PROGRESS.md` in batches (end of a step, or after a real decision
  change) — not after every small substep: mark step statuses, add a dated
  entry to the session history log, and note any new decisions or open
  questions.
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
