# RallyQuery — 9-10 Elevation Backlog

The base build (`PLAN.md`, steps 0-19) gets this project to a strong ~8/10:
a well-engineered, production-shaped NL→SQL agent with guardrails, eval, and
deployment. That's a known project category executed with unusual rigor.

To push past that into genuinely rare territory, these are the specific
upgrades identified and why each matters. These are additive — pursue them
whenever there's appetite, independent of the base-plan step numbering.
Track status here so nothing gets lost across sessions.

| # | Upgrade | Why it matters | Status |
|---|---|---|---|
| 1 | **Real CV→data pipeline bridge** — feed `rallies`/`shots` tables from actual tracked output (even a small YOLO/pose model run on sample rally footage, or a public tracking dataset), not pure Faker | Turns the sports theme from *narrative* branding into a *technical* bridge between the resume's CV work and this GenAI project — the single highest-leverage change, and a rare combination (real-time CV + agentic LLM systems) | not started |
| 2 | **Real, messy public data** — merge in real ATP/WTA match/ranking data alongside synthetic rally/shot detail | Real data has real inconsistencies the guardrails/introspection must survive — more defensible than self-generated messiness | not started |
| 3 | **Public usage + real failure cases** — share the live demo somewhere real (community, LinkedIn), collect actual questions people ask, fold failures into the eval set | "Here are real failures a stranger hit and how I fixed them" beats a self-authored eval set; shows product thinking, not just engineering | not started |
| 4 | **Deeper agent reasoning** — clarifying-question behavior for genuinely ambiguous queries instead of guessing; decomposition of complex analytical questions into sub-queries | Shows agent *design*, not just a generate→validate→retry loop | not started |
| 5 | **Adversarial security pass** — documented red-team attempts against the guardrails (prompt injection, SQL injection, jailbreaks), mapped to OWASP LLM Top 10, with what got through vs. blocked | Almost no portfolio projects show adversarial testing against their own claimed guardrails — this is a credibility multiplier | not started |
| 6 | **Public write-up** — a detailed post or README section on the guardrail design and schema-retrieval approach, published somewhere visible | Citable public work outweighs a private repo in how it gets evaluated | not started |

## Sequencing guidance

Item 1 should be considered early if pursued at all — it affects the seed
data step (Step 1 in PLAN.md), so retrofitting it later means re-touching
the DB layer. Items 2-6 can be layered on after the base agent works without
disrupting earlier steps.

None of these block shipping the base plan. The user is handling overall
tiering/prioritization directly — this file exists so the upgrade ideas
aren't lost across sessions, not to gate progress on completing them.
