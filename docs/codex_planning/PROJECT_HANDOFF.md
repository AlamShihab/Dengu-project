# Continuation handoff

## Current request

Build daily dengue forecasts for Days 1–7, district first, division also supported, upazila if reliable history exists. Match the user's weather project at:

`C:\Users\USER\Desktop\Shihab\Niaz Bhai\Weather_ML\Final Work File`

The current turn was **planning first**, plus creation of durable continuation files. Implementation must not be reported as complete on the basis of this plan.

## Master dengue folder

`C:\Users\USER\Documents\Codex\2026-10-11\you\outputs\bd-dengue-monitor`

This is the app built in this conversation and the chosen continuation root. Another project exists at `C:\Users\USER\Desktop\Shihab\Personal\Project\Disease Surveillance Dashboard\bd-health-signals`; it was inspected only. Do not split future outputs between these roots or silently replace either project. If the user later requests moving the master folder, preserve data and history and update all path references.

## Completed

- Existing local monitoring V1: React dashboard, Python ingestion/import service, validated official source fetch, revision/raw-release retention. Prior build verification: 16 backend + 7 metric tests passed. See BUILD_LOG.md and VERIFICATION.md. These are prior V1 checks, not forecast-model validation.
- Read weather app README, user manual, Flask templates/CSS, pipeline stages, model configuration, feature contract, and inference source. Its actual implementation overrides aspirational prompt-document descriptions as a reference.
- Profiled both local dengue datasets with `scripts/inspect_forecast_readiness.py`; saved file fingerprints and series coverage.
- Found a published 2026 study reporting daily district-level DGHS admissions for 2022–2025. This is a source lead, not an acquired/validated training dataset.
- Wrote forecasting plan, reference audit, data readiness notes, task state, and logs.

## Important findings

- Active app has 30 national daily observations, 12 Sep–11 Oct 2026, and one date of 10 division/city reporting units: 40 rows total. No district/upazila histories.
- Separate Desktop project has 608 metric rows: 283 national daily admissions-labelled-as-new_cases observations and 283 daily deaths, 1 Jan–10 Oct 2026, plus aggregate snapshots. These counts were profiled, not independently reconciled to source in this turn.
- Its geographic lookup has 8 division, 64 district, and 544 rows labelled upazila. The last count needs an authoritative administrative-type audit; do not assume all are current upazilas. Geographic reference rows are not dengue observations.
- Weather forecasts use horizons 1,2,3,5,7,10,13,15, a 17-model registry, direct per-horizon inference, expanding-window CV, and Flask/Plotly UI. Dengue horizons must instead be exactly 1–7.
- Weather uncertainty uses ±1.2816 × test RMSE. Do not copy that into dengue forecasts; use separately calibrated count prediction intervals without fitting to held-out test outcomes.
- Weather setup has only maximum temperature, with filled values documented. It is not a ready district rainfall/humidity feed. Reuse the software pattern, not its trained weights or weather data assumptions.

## Next action when implementation starts

Execute **F01: district source and geography feasibility audit** in IMPLEMENTATION_PLAN.md. First inspect a small representative sample of actual DGHS district releases spanning multiple dates/years; establish daily admissions semantics, facility vs residence geography, Dhaka coverage, raw availability, and a lawful reproducible collection route. Update the source register with samples and hashes. Acquire/validate history before fitting any district model. Upazila acquisition is parallel optional scope, not a reason to postpone eligible district work.

Implement the reusable forecast application shell alongside the data work, but leave forecast actions disabled with explicit missing-data/model reasons until validated outputs exist. Proposed sibling directories inside this root: `forecasting/app/` and `forecasting/pipeline/`. This is a proposal, not an already-created app.

## Commands that exist now

From the master dengue root:

```powershell
& "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" scripts/inspect_forecast_readiness.py
& "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m monitor serve
```

The second command serves the existing monitoring V1 on port 8765. A server was left running in the previous build turn; probe before starting another process. Never kill an unrelated process to reclaim a port.

No forecast training command is implemented yet. No model is running, no API key is needed for planning, and no public publication or scheduled job has been activated. Model runtimes and data acquisition estimates remain conditional on F01.

## Session close requirement

Record data snapshots, config hashes, split definition, model/run IDs, partial-run progress, validation results, unresolved issues, and exact next command. A later LLM should be able to resume without redoing completed stages or mistaking a proposed artifact for a real one.
