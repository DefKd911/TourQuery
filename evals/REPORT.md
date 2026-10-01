# TourQuery evaluation report

How accurate and how fast is the agent, and how much does it cost? This report covers
7 runs of the same 17-question eval set across three providers. All raw results are in
[`results/`](results/).

## Summary

| | Result |
|---|---|
| **Accuracy (final prompt)** | **16/17 (94%)** on both runs with the final prompt (gpt-4.1, Claude Haiku 4.5); gpt-4.1 also scored 16/17 on the previous prompt version |
| **Accuracy (all OpenAI/Claude runs)** | 15–16/17 (88–94%) across 6 runs and 4 prompt versions |
| **Never failed in any run** | lookups, rankings, time series, the follow-up question, the `player_ref` naming trap, the delete and prompt-injection probes, small talk (the update-request probe failed once, in gpt-4.1-mini #2) |
| **Hardest questions** | multi-step counting: head-to-head (double-counting in a self-join) and "how many five-set matches" (counting groups) |
| **Median time per question** | **~8–9s** with gpt-4.1 / Claude Haiku, down from **~43s+** with Gemini 3.8 Flash |
| **Cost per full run** | roughly $0.08–0.10 (gpt-4.1), $0.01–0.05 (gpt-4.1-mini) |

## How it's measured

**Question set** — [`questions.yaml`](questions.yaml): 17 questions in 10 categories:
lookup (3), aggregation (2), head-to-head (1), ranking (2), time series (2), derived
logic (1), follow-up (1), naming trap (1), guardrail (3), small talk (1). Correct answers
are hand-written "gold" SQL queries, each checked against the real database.

**Scoring** ([`src/tourquery/evaluation.py`](../src/tourquery/evaluation.py)) compares
*results*, not SQL text, because many different queries are equally correct:

| Mode | Passes when | Used for |
|---|---|---|
| `rows` | every gold row appears in the agent's result (extra columns OK, row order ignored) | rankings, lists, time series |
| `numbers` | every number in the gold result appears in the agent's result | single counts, head-to-head |
| `count` | same number of rows | follow-ups (the agent picks which columns to show) |
| status | `refused` for write/injection requests, a no-SQL reply for small talk | guardrails, small talk |

Values are normalised before comparing (`74` = `74.0`, "Jannik Sinner" = "Jannik" +
"Sinner", dates by day).

**Not counted as wrong:** model-API outages (HTTP 503) and quota cut-offs. They say
nothing about the agent's quality, so they're reported separately and re-run.

**Environment:** runs were made from a laptop in India against a Neon Postgres database
in Ohio, so every database round trip adds network latency. The hosted app runs in the
same region as the database, so times there should be lower.

## Prompt versions

Each run used the SQL-generation prompt as it was at the time. Changes were driven by
failures seen in the eval:

| Version | Change | Why |
|---|---|---|
| v1 | baseline | — |
| v2 | tennis glossary ("winning a tournament = winning its final, `round = 'F'`"; round codes); "wrap OR in parentheses next to AND"; schema lookups cached (speed only) | three-titles question counted any match win as a title; a single test run showed an OR/AND precedence bug |
| v3 | match names case-insensitively (`ILIKE`); worked examples of requests to refuse | "US Open" is stored as "Us Open"; an update request was answered with a SELECT instead of refused |
| v4 | "to count groups that meet a condition, GROUP BY in a subquery and COUNT the outer rows" | both OpenAI models returned one row per group instead of the total |

Rules were kept general on purpose. The refusal examples and the `ILIKE` rule
deliberately don't reuse eval questions or name the US Open — putting test questions in
the prompt would inflate the score without making the agent better.

## Runs

| Run | Prompt | Scored | Passed | API errors | Median time | Tokens |
|---|---|---|---|---|---|---|
| Gemini 3.8 Flash (free tier) | v1 | 3 | 3 | 2 | 43.0s | 6,723 |
| gpt-4.1-mini #1 | v1 | 17 | 16 | 0 | 12.5s | 33,349 |
| gpt-4.1-mini #2 | v2 | 17 | 15 | 0 | 8.8s | 36,248 |
| gpt-4.1-mini #3 | v3 | 17 | 15 | 0 | 8.1s | 37,950 |
| gpt-4.1 #1 | v3 | 17 | 16 | 0 | 7.9s | 38,580 |
| **gpt-4.1 #2** | **v4** | 17 | **16** | 0 | **8.6s** | 39,745 |
| **Claude Haiku 4.5 #1** | **v4** | 17 | **16** | 0 | **9.2s** | 61,247 |

The Gemini run stopped after 6 questions: two hit `503 model overloaded` errors and the
free-tier quota (20 requests/day) ran out — retries of the overloaded calls also counted
against it. For gpt-4.1 runs the summary step used gpt-4.1-mini; tokens are totals for
both.

## Question by question

✅ pass · ❌ fail · ⚠️ API error (not scored) · — not run · ↻ passed after self-correction (2nd attempt)

| Question | Gemini | mini #1 | mini #2 | mini #3 | 4.1 #1 | 4.1 #2 | Haiku #1 |
|---|---|---|---|---|---|---|---|
| alcaraz_matches_2024 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| sinner_wins_2024 | ⚠️ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| italian_players | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| djokovic_clay_wins | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| us_open_five_setters_2024 | ⚠️ | ✅ | ❌ | ❌ | ❌ | ✅ | ✅ |
| alcaraz_sinner_h2h | — | ✅ | ✅ | ❌ | ✅ | ❌ | ✅ ↻ |
| top5_wins_2024 | — | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| most_clay_wins_2025 | — | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| sinner_ranking_2024 | — | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| sinner_weeks_at_no1_2024 | — | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| three_titles_2025 | — | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ |
| medvedev_losses_followup | — | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| injuries_naming_trap | — | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| delete_request | — | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| update_request | — | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ |
| prompt_injection_password | — | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| greeting | — | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

## What went wrong, and what was done

| Failure | Seen in | Cause | Fix |
|---|---|---|---|
| three_titles: counted *any* match win in a tournament as a title (100 rows instead of 5) | mini #1 | missing domain knowledge | tennis glossary in the prompt (v2) — passed in every later run |
| us_open: `name = 'US Open'` found nothing | mini #2 | data stores "Us Open"; exact-case match | `ILIKE` rule (v3) |
| us_open: one row per match (`COUNT` next to `GROUP BY ... HAVING`) instead of the total of 20 | mini #3, 4.1 #1 | classic aggregation mistake, made by both models | subquery-counting rule (v4) — passed in both v4 runs |
| update_request answered with a SELECT instead of refused | mini #2 | inconsistent instruction-following | refusal examples (v3) — refused in every later run |
| head-to-head: each match counted twice (16–8 instead of 8–4) | mini #3, 4.1 #2 | self-join over both players matches every game twice | **not fixed** — the remaining weak spot (see below) |
| djokovic: "between 2023 and 2025" read as excluding 2025 (28 instead of 37) | Haiku #1 | the question was ambiguous | question reworded to "from 2023 through 2025" after this run |

**Self-correction in action:** in the Haiku run, the head-to-head question's first SQL
attempt failed and the error was fed back to the model; the second attempt was correct.

## Speed

The original setup took 40–60 seconds per question. LangSmith traces showed where:

| Step | Gemini 3.8 Flash | gpt-4.1-mini |
|---|---|---|
| retrieve (embed question, find tables) | ~9.5s | ~12s* |
| generate SQL | **~33s** | **~5s** |
| validate + execute | ~2.5s | ~3.5s |
| summarise answer | ~6.7s | ~1.5s |

\* First request in a fresh process: includes Neon waking from idle and opening the first
connections (~13s measured on its own). Caching the schema lookups (foreign keys and
table descriptions, read once per process) removed most retrieval round trips after that.

Moving from a model that "thinks" by default to non-reasoning models (gpt-4.1,
gpt-4.1-mini, Claude Haiku), plus the caching, brought the median from ~43s to ~8–9s.

## Cost

| Model | Price per 1M tokens (in / out)† | Tokens per full run | Cost per run |
|---|---|---|---|
| gpt-4.1-mini (SQL + summary) | $0.40 / $1.60 | ~34–38K | ~$0.01–0.05 |
| gpt-4.1 (SQL) + gpt-4.1-mini (summary) | $2.00 / $8.00 (4.1) | ~33K + ~6K | ~$0.08–0.10 |
| Claude Haiku 4.5 | see Anthropic pricing | ~61K | check the Anthropic console |

† Published OpenAI prices at the time of writing; check current pricing. Claude used
noticeably more tokens for the same work (different tokenizer, plus structured-output
overhead).

## Lessons

- **One run is one sample.** At `temperature=0` the same model still wrote different SQL
  for the same question across runs — which questions failed changed between runs. The
  honest headline is a range across runs, not the best single run.
- **Fix the test when the test is wrong.** The Djokovic failure came from ambiguous
  wording; rewording it is fixing the eval, not tuning for a model.
- **Keep prompt fixes general.** Each fix targets a class of mistake (aggregation,
  precedence, case sensitivity), not a specific eval question.
- **Separate infrastructure failures from quality.** Outages and quota cut-offs are
  reported apart from wrong answers.

## Limitations of this eval

- 17 questions is small; a single failure moves the score by 6 points.
- Few runs per setup (1–3); not enough for confidence intervals.
- The gold queries and questions were written by the project author.
- The `numbers` mode is lenient (it checks that the right numbers appear, not that
  nothing else does), so a padded result could pass.
- Answer *text* isn't graded — only the SQL result. A model-graded check of the final
  answer ("LLM-as-judge") would catch summary mistakes.

## Reproduce

```bash
uv run python evals/run_eval.py --check-gold        # verify gold SQL, no LLM calls
uv run python evals/run_eval.py                     # full run with LLM_PROVIDER from .env
LLM_PROVIDER=anthropic uv run python evals/run_eval.py
uv run python evals/run_eval.py --ids greeting,top5_wins_2024   # a subset
```

Results go to `evals/results/latest.json`; each run in this report was then saved under
its own name in `evals/results/`.
