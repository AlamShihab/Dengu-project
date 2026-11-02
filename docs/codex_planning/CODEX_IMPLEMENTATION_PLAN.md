# Bangladesh dengue forecasting — implementation plan

Prepared 12 October 2026. **Status: plan prepared; forecast implementation/training has not started.**

## 1. Required product

Recreate the user's Weather_ML application format for dengue: Dashboard, Make Forecast, Model Performance, Upload Data; same visual structure, local charts, model leaderboard, run progress, versioned data, result downloads, light/dark and mobile behavior. Add a Project Log entry for continuation.

The primary forecast is daily reported dengue admissions for each eligible **district**, with **division** support and **upazila/subdistrict** support where data passes the same checks. Always produce the complete sequence **Day 1, Day 2, Day 3, Day 4, Day 5, Day 6, Day 7**, not a single seven-day sum. A total may be shown additionally.

The earlier claim-checker idea is not the active direction. News/AI claim extraction is not part of this forecast build.

## 2. Output and date contract

- Each row: `run_id, issue_date, issued_at, data_as_of, geo_level, geo_code, parent_code, horizon, target_date, target_metric, geography_basis, prediction, lower_80, upper_80, model_id, data_version, model_status, warnings`.
- Horizon `h` means target calendar date `issue_date + h` in Asia/Dhaka. Exactly seven consecutive future dates are returned for a current forecast. `data_as_of` is separate from `issue_date`.
- Missing the current day's report does not shift forecast dates silently. Support an explicitly validated reporting-delay configuration (for example a one-day delay, with the same feature masking in backtests); otherwise show unavailable/current-data-needed. Old-origin results may be explored as historical forecasts with their real dates, never as current next-seven-day predictions.
- Estimate daily admission counts; retain numeric precision in exports, use understandable rounded display, keep point estimates and interval bounds nonnegative. Intervals are predictive ranges, not guaranteed limits.
- Unavailable horizons/places have status and reasons, not zeros. Default the UI to the full seven-day outlook.
- For comparisons or aggregation, use a common issue date, target dates, target definition and data-availability policy.

## 3. Geographic behavior

Use hierarchical selectors: Division → District → Upazila, plus a level selector and an All eligible places view. List coverage/availability explicitly.

- District is the main delivery target. Build division forecasts from valid same-basis district coverage, or train a separately labelled direct division model where verified division history exists.
- Upazila is optional. Display unavailable when there is no validated daily history. Offer the district forecast with an explicit district label; never relabel it as an upazila prediction or allocate district totals by population and call them observations.
- Preserve official geography codes and dated parent relationships; resolve Dhaka city/excluded-city categories before aggregating.
- When complete district coverage supports bottom-up division totals, sum point forecasts. Do not sum individual lower/upper bounds and call the result an 80% interval: use a jointly calibrated aggregate model or joint residual simulation. If coverage is partial, label it partial and do not claim a full division total.

## 4. Structure inside this dengue project

```text
bd-dengue-monitor/
  START_HERE.md
  PROJECT_HANDOFF.md
  PROJECT_STATE.json
  BUILD_LOG.md
  docs/forecasting/
    IMPLEMENTATION_PLAN.md
    WEATHER_REFERENCE_AUDIT.md
    DATA_READINESS.md
    readiness-profile.json
  logs/
    SESSION_LOG.jsonl
    DECISIONS.md
  forecasting/                     # proposed; created during implementation
    app/                          # adapted Flask/Jinja/Plotly reference UI
      app.py, config.py, pipeline_runner.py, data_versions.py
      templates/, static/, tests/, run_app.bat, USER_MANUAL.md
    pipeline/
      train_pipeline.py
      config/                     # source, geography, features, models, splits
      src/, scripts/, tests/
      data/raw/, data/validated/, data/processed/, data/features/
      models/current/, models/archive/, model_metadata/
      predictions/, results/figures/, experiments/, logs/
  monitor/, data/, src/, dist/     # existing monitoring V1 preserved
```

Keep the reference weather project read-only. Adapt code into the dengue project; no cross-project Python imports or dependency on weather model artifacts. Use a separate environment and a configurable local port (proposed 8766) to avoid weather port 5000 and current monitor port 8765. Later make the forecast app the preferred launcher only after it passes acceptance checks. Do not rewrite protected React runtime files; the requested Flask format is implemented alongside the existing monitor.

## 5. Stages and acceptance gates

| ID | Stage | Deliverable / exit condition |
|---|---|---|
| F00 | Reference audit and plan | This plan, actual file audit, data profile, state and logs — completed |
| F01 | Source/geography feasibility | Sample real district releases across dates/years; source register; definitions; geographic crosswalk; explicit district/upazila feasibility conclusion |
| F02 | Acquire and validate history | Immutable raw releases, versioned daily dataset, missingness/revision flags, per-unit coverage and eligibility report |
| F03 | Forecast app foundation | Weather-format pages, hierarchy selectors, upload preview, logs and honest no-model states; shared config and adapters |
| F04 | Preparation, splits, features | One row per unit/date; frozen development/calibration/test periods; availability-aware lag/rolling features; leakage audit |
| F05 | Baselines and candidate screening | Resumable runs and per-horizon/per-unit leaderboards on development folds |
| F06 | Tuning, uncertainty and evaluation | Selected models, calibrated intervals, untouched test predictions, error/coverage reports and promotion decision |
| F07 | Forecast service and complete UI | Day 1–7 outputs for eligible units; all-place tables; model performance; exports; update/refit workflow; data/model recovery |
| F08 | Acceptance and handoff | Backend/model/temporal tests; weather-format visual comparison; desktop/mobile browser checks; instructions and final continuation log |

F01–F02 are the critical dependency for district forecasts. F03 can proceed while source collection is resolved. A completed UI is not evidence that district forecasting works.

## 6. Data engineering

Initially target official daily reported admissions. Acquire enough history to cover multiple dengue seasons, preferably 2022 onward if the original district reports are accessible. Two seasonal cycles are an engineering target, not a guarantee of accuracy.

Store raw releases unchanged and retain original-observation flags. Standardized tables include `report_date, available_at, geo_code, geo_level, metric, value, geography_basis, source_id, release_id, revision, observed_flag, qc_status`. Keep geography in a separate dated parent-child registry.

Never turn an absent district/day into zero without evidence of an explicit zero report. Missing targets stay missing; do not train or evaluate on interpolated dengue targets. Feature imputation, if used, must be causal and fitted within training folds. Preserve valid outbreak peaks. Keep correction history and model-data hashes.

Start with a documented eligibility configuration; finalize thresholds from the data profile before comparing models. Evaluate history span, observed target count, missingness, recent completeness, publication delay, geographic stability, and number of usable validation/test origins. Sparse units can have validated baseline forecasts or no forecast; they do not automatically receive an ML claim.

Use historic report availability/revisions where recoverable. If only final revised counts exist, label backtests as retrospective and simulate plausible publication delays; do not claim they recreate exact live information.

## 7. Models and features

Preserve the weather pipeline's configurable registry and staged screening/tuning. The first screen should be small enough to finish and inspect:

- Baselines: last observed count (persistence), trailing seven-day mean, same-weekday/seasonal-naive where history exists. Seasonal terms only when supported by history.
- Candidates: a Poisson count regression, histogram gradient boosting with a count-compatible objective, and one tree ensemble comparator. LightGBM/XGBoost/other weather-registry families may be added after dependency and data checks; the 17-family weather sweep is not copied automatically.
- Train **seven direct horizon models pooled across eligible districts**, with appropriate categorical geography handling. This shares information without requiring 448 independently tuned district models. Evaluate whether local/region-specific models improve supported units before adding them.
- Inputs: lagged admissions; trailing means/totals and changes; weekday and seasonal calendar features; district identity; quality/availability flags. All windows end at the latest information actually available at issuance.
- Optional rainfall, humidity and temperature features are a later comparison, not a blocker for the first admissions-only model. The weather reference contains Tmax only. Obtain verified geographically matched observations; future weather may be used only from forecasts issued before the dengue forecast, with equivalent archived availability in backtests. Do not insert realized future weather into training or evaluation features.

Keep a serialized feature contract, schema and hashes so training and inference use identical transformations. Do not reuse temperature model weights or presume weather-data cleaning is valid for dengue.

## 8. Evaluation, intervals and promotion

- Use chronological expanding-window backtests; all units in a fold share date boundaries. Purge origins whose targets cross the next fold boundary, with a horizon-aware gap of at least seven days where needed. Fit preprocessing on training folds only.
- Reserve a chronologically later calibration period and a final untouched test period, with adequate seasonal representation as history permits. Freeze them before tuning. Do not use the final test set to choose hyperparameters, interval widths or winning models.
- Primary point metric: MAE in admission counts. Also show RMSE, bias, baseline-relative skill and usable test-date counts. Report macro district averages as well as burden-weighted/micro summaries to avoid hiding small-district failures. MAPE is not a primary score because zero counts can occur.
- Report each Day 1–7 separately and break out district/division performance, high-burden periods, low-count periods, coverage and unsupported units.
- Fit nominal 80% count prediction intervals from development/calibration residuals or quantile models, respecting nonnegativity and temporal split boundaries. Measure actual coverage, width and interval score on held-out dates. Weather's `prediction ± 1.2816 × test RMSE` is not adopted.
- Select candidates against simple baselines using development validation. A documented final test failure blocks promotion and triggers a new version/review, not repeated tuning against the same test labels. Deploy a validated baseline where justified; withhold unsupported forecasts.
- Save predictions as issued and later join finalized actuals for prospective scoring. Daily score history is needed to distinguish retrospective skill from live performance.

## 9. Application behavior matching Weather_ML

| Page | Dengue behavior |
|---|---|
| Dashboard | Data as-of date, eligible/unsupported places, deployed models, error by horizon, data quality, training state, figures and downloads |
| Make Forecast | Level + hierarchical place selection; Day 1–7 outlook by default; daily prediction/range/date; recent history and forecast; all eligible district matrix; CSV/JSON |
| Model Performance | District/level and horizon filters; baseline comparisons, MAE/RMSE/bias, coverage/interval score, residuals, feature importance with association-only interpretation |
| Upload Data | CSV/XLSX preview → validation → explicit apply; source/metric/geography checks; retained versions; data/refresh/full mode; progress and cancellation |
| Project Log | Current task, completed stages, last run, blockers, next step, model/data IDs and downloadable handoff |

Use a thin Flask API that calls the shared pipeline engine; no duplicate feature logic in JavaScript. Proposed endpoints mirror the reference: `/api/locations`, `/api/forecast`, `/api/outlook`, `/api/forecast-all`, `/api/model-metrics`, `/api/data-status`, `/api/upload`, `/api/apply-data`, `/api/pipeline-run`, `/api/project-status`.

Updates are transactional. Preview does not commit. Keep old data/models until replacement validation completes. Cancellation/failure retains the currently deployed model. Uploading data alone does not refresh published accuracy. A new evaluation period creates a new version; it does not silently overwrite historical evaluation.

## 10. Continuation and operational logs

Maintain root `START_HERE.md`, `PROJECT_HANDOFF.md`, `PROJECT_STATE.json`, `logs/DECISIONS.md`, and append-only `logs/SESSION_LOG.jsonl`. Each entry records date/time, objective, actions, changed files, checks/results, blockers, and exact next step.

Every model run records a UUID, code version/fingerprint, config/feature/data/geography hashes, source vintage policy, split hash, random seed, package versions, fold/horizon status, durations, metrics and artifact paths. Checkpoint by stage/model/horizon/fold. Reuse a checkpoint only if its input/config fingerprints match. Keep accepted artifacts under models/current and earlier artifacts under models/archive.

At session end, state whether a process is still running and how to inspect/stop that specific process. Never leave the next LLM to infer whether a training command completed. Never store secrets in logs or handoff documents.

## 11. Acceptance criteria

1. Every enabled district returns seven correctly dated daily forecasts or a structured reason why it cannot.
2. Days 4 and 6 are tested explicitly; leap days, Dhaka midnight, stale observations, and reporting delays have tests.
3. Targets, geographic basis and missingness are correctly labelled. No unsupported upazila forecasts or fabricated data are displayed.
4. Model metrics are reproducible from saved out-of-sample predictions and compare against baselines.
5. Intervals are calibrated separately from the test set and their achieved coverage is displayed.
6. Aggregation respects geography coverage; division uncertainty is not obtained by naive endpoint addition.
7. Upload, correction, restore, failure and cancellation preserve the last accepted system state.
8. The four primary pages follow the weather reference; source and browser visual QA confirm behavior at desktop/mobile widths.
9. A new session can resume using START_HERE without reading the chat.

## 12. Delivery estimate and current limit

After usable district history is available, allow roughly **8–12 focused development days** for the staged implementation, calibration, UI integration and verification. This is a planning estimate, not a committed deadline; source acquisition and long experiments are separate uncertainties. The first feasibility milestone should take about 1–2 working days if accessible sample releases exist.

Current result is the plan and continuation system. District data acquisition, training, forecast accuracy and upazila feasibility remain uncompleted. No public health risk class, outbreak alarm, diagnosis, or automatic operational decision is promised by these admission forecasts.
