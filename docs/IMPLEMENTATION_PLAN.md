# Dengue Forecasting System (DFS) — Implementation Plan

Written 2026-10-12 by Claude Code (Opus 5.5) for Shihab. **Status: approved and implemented on 2026-10-12** (see
`docs/PROGRESS_LOG.md` for results and §10 below for what changed during implementation).
Progress is tracked in `docs/PROGRESS_LOG.md`; tick the boxes below as stages finish.

## 1. Goal

Forecast **daily dengue hospital admissions** for each **division** and **district** of Bangladesh for the next
**7 days, every day separately: Day 1, 2, 3, 4, 5, 6, 7**. Show the forecasts in a web app built **exactly like the
Weather_ML Temperature Forecasting System (TFS)**:
`C:\Users\USER\Desktop\Shihab\Niaz Bhai\Weather_ML\Final Work File`. The same staged training pipeline, the same
Flask app pages, the same API pattern, and the same run modes and logs.

Upazila (subdistrict) forecasts are **not possible with public data**: DGHS publishes nothing below district level
(see `docs/DATA_SOURCES.md`). The upazila selector stays in the app. It says so clearly and shows the parent
district's forecast, labelled as a district forecast. If upazila data is obtained later, it plugs into the same pipeline as
another `geo_level`.

## 2. Data (verified 2026-10-12, details in `docs/DATA_SOURCES.md`)

- **Source:** DGHS *Daily Dengue Press Release* PDFs,
  `https://dashboard.dghs.gov.bd/osource/images/docs/vpr/YYYYMMDD_dengue_all.pdf`, listed on
  `https://dghs.gov.bd/pages/static-pages/dengue-press-release-gxrgtg-6a9eb4cc7a024513d1b8c896`.
- **Coverage:** 2021-12-13 → **2026-09-03**: 2022 365 days, 2023 365, 2024 360, 2025 365, 2026 246. About 1,720
  PDFs of about 1.1 MB each, roughly 2 GB.
- **District table:** a table per division listing every district plus named medical-college hospitals:
  *new admissions in last 24 h (government / private / total)*, *admissions since 1 January*, *deaths*, *discharged*,
  *currently admitted*. It is present in the 2022, 2024 and 2026 samples. The text layer is Unicode Bangla with Bangla
  digits, so it parses with PyMuPDF and needs no OCR. Some district names come out with mangled glyphs; an alias table maps them.
- **Dhaka city:** Dhaka metropolitan hospitals are listed hospital-by-hospital on separate pages. The Dhaka district
  row is "Dhaka (excluding metropolitan)".
- **Gap:** no PDF after **2026-09-03** (404s). The live DGHS dashboard has only national + division/city-corporation
  figures. District forecasts can therefore only start from 2026-09-03 until newer district data is uploaded or DGHS
  resumes publishing (see §8).

## 3. What gets forecast

| Item | Decision (Shihab can override) |
|---|---|
| Target | New dengue hospital admissions reported in the last 24 h (DGHS report day = 24 h ending 8 am) |
| Geography basis | **Hospital location** (where the patient was admitted), not patient residence. Shown on every page |
| Forecast units, district level | 64 districts, with **Dhaka Metropolitan (city hospitals)** as its own unit, 65 units in total. "Dhaka district total" = Dhaka Metro + Dhaka outside metro, shown as a sum |
| Forecast units, division level | 8 divisions (direct models on division totals; checked against the sum of district forecasts) |
| Upazila | Not available. The app shows a clear message plus the parent district forecast |
| Horizons | 1, 2, 3, 4, 5, 6, 7 days. One **direct** model per horizon per level (like TFS), pooled across all units |
| Origin | t = latest report date with data. Day h = report date t + h |
| Range | 80% prediction interval, calibrated on cross-validation out-of-fold errors and never negative. TFS's ±1.28×RMSE is **not** reused (counts are skewed) |
| Deaths | Not forecast in v1 (counts too small). Shown as context only |

## 4. Folder layout (mirrors TFS: `Work with claude/` → `pipeline/`, `app/` → `app/`)

```text
dengue-forecast/
  CLAUDE.md                 project context for Claude Code (like TFS CLAUDE.md)
  AGENTS.md                 pointer for Codex / other LLMs
  docs/
    IMPLEMENTATION_PLAN.md  this file
    PROGRESS_LOG.md         session-by-session log + current status + next action
    DATA_SOURCES.md         source evidence
    source_samples/         sample page images, URL list, hashes
    codex_planning/         Codex's earlier plan (reference only)
  pipeline/                 training pipeline (= TFS "Work with claude")
    config/                 config.json, geography.json, features.json, models.json, tuning.json
    src/                    reusable modules (ingest, pdf_parser, validation, preparation, splitting,
                            feature_engineering, baselines, model_registry, screening, tuning, training,
                            evaluation, forecasting, audit, reporting, utils, paths, config)
    scripts/                00_download_pdfs.py, 00_parse_pdfs.py, 01_validate.py … 09_evaluate.py
    train_pipeline.py       stage runner (--list / --only / --from), as in TFS
    data/raw/pdfs/YYYY/     original PDFs (never modified, sha256 manifest)
    data/raw/               dengue_daily.csv (parsed, long format)
    data/validated|processed|features/
    results/ models/current|archive/ model_metadata/ predictions/ experiments/ logs/
    tests/
  app/                      Flask web app (= TFS "app")
    app.py config.py pipeline_runner.py data_versions.py
    templates/ static/ tests/ run_app.bat run_app.ps1 README.md USER_MANUAL.md
```

The weather project stays **read-only**. Code is adapted (copied and changed) into this folder. Nothing imports from the weather
project, and no weather model files are used. Own `.venv` (Python 3.12 via uv). The app runs on port **5001** (TFS uses 5000).
A git repo in `dengue-forecast/` with one commit per stage, as in TFS. Raw PDFs and generated data are git-ignored.

## 5. Stages (TFS "Day" structure; one "day" = one work session, not a calendar day)

### Stage 0 — Acquisition (new; TFS was handed a data file)
- [x] `scripts/00_download_pdfs.py`: download every `vpr` PDF (2021-12-13 → latest), 1 request every 2 s,
      identifying User-Agent, resumable, `data/raw/pdfs/manifest.csv` (date, url, http status, bytes, sha256,
      downloaded_at). `--update` fetches only new dates (tries yesterday … +N days so it picks up DGHS resuming).
      About 1 h in the background.
- [x] `src/pdf_parser.py` + `scripts/00_parse_pdfs.py`: PyMuPDF words with coordinates → table rows.
      Parse (a) the district table: division, district, institution, 24 h gov/private/total, cumulative admissions, deaths,
      discharged, currently admitted; (b) the Dhaka metro hospital table; (c) the page-1 national/division totals.
      Bangla digits → ints. District aliases (mangled glyphs → BBS code) in `config/geography.json`, built from
      `bd-health-signals/data/reference/gazetteer.csv` + `names_bn.csv` + observed variants.
      Output `data/raw/dengue_daily.csv`: `report_date, geo_level, unit_code, unit_name, division_code,
      admitted_24h_gov, admitted_24h_private, admitted_24h, cum_admitted, cum_deaths, cum_discharged,
      currently_admitted, source_file, sha256, page, parse_version`.
- [x] Layout handled per year (2022 pages 4–5, 2024 pages 7–9, 2026 pages 8–10; detect by headers, not page numbers).
- [x] Hand-check against the PDF images: 2 days per year (≈10 days), every number of the district table. The test fixtures
      come from these days.

### Day 1 — Setup
- [x] Folders, `git init`, `.venv` (pandas, numpy, scikit-learn, lightgbm, xgboost, catboost, optuna, pymupdf,
      pyarrow, joblib, matplotlib, flask, openpyxl, pytest), `config/*.json`, `src/config.py`, `src/paths.py`,
      `src/utils.py` (copied from TFS and adapted), `train_pipeline.py` with stage list, `00_check_environment.py`.

### Day 2 — Validation & QC (`01_validate.py`, `results/01_*`)
- [x] Missing report dates, duplicate dates, unknown/unmapped districts (blocking).
- [x] Sum of districts + institutions + Dhaka metro = division row = page-1 division figure = national total.
- [x] Cumulative consistency: `cum_admitted(t) − cum_admitted(t−1)` vs `admitted_24h(t)` (catches parse errors and
      DGHS revisions; flagged, never silently changed). Year-start reset on 1 January.
- [x] Negative/implausible values, stuck values, sudden jumps → flags (blocking / error / warning / info, as TFS).
- [x] Never delete data: row-level flags in `data/validated/01_row_flags.parquet`.

### Day 3 — Preparation & EDA (`02_prepare.py`, `03_eda.py`)
- [x] Daily panel: one row per unit per report date, gap-free calendar, `is_observed / is_missing` flags. Missing days stay
      missing (no interpolated targets). An explicit zero in the table counts as observed.
- [x] Unit eligibility (enough observed days, recent data) → `results/02_unit_eligibility.csv`.
- [x] EDA: seasonality (Aug–Nov peaks), weekday reporting effect, autocorrelation by lag, district shares, the 2023
      outbreak, 2026 season so far. Figures in `results/figures/`.

### Day 4 — Split & leakage control (`04_split.py`)
- [x] Proposed (final after EDA): **development** origins 2022-01-08 → 2025-06-23, **7-day embargo**,
      **test** origins 2025-07-01 → 2026-08-27 (the whole 2025 season and 2026 so far). Post-test data = forecast inputs only.
- [x] CV: expanding folds with 6-month validation blocks (e.g. 2023-H2, 2024-H1, 2024-H2, 2025-H1) and a 7-day gap.
- [x] Leakage guards adapted from TFS `leakage.py` (targets after origin, folds chronological, shift test).

### Day 5 — Features (`05_features.py`, `config/feature_contract.json`)
- [x] Per unit at origin t: lags 0–13, rolling mean/sum/max 3/7/14/28 (ending at t), 7-day growth ratio,
      `currently_admitted` (inpatients, a leading indicator), cumulative-season level, deaths 7-day sum.
- [x] Context: own-division and national lags/rolling means; district population (Census 2022) → rates per 100k.
- [x] Calendar: day-of-week of target, day-of-year sin/cos, month, epi-week, year. Unit code (categorical), division.
- [x] Target `y_h{h}` = admissions at t+h, observed only. `build_features()` is one function for training **and**
      forecasting, as in TFS.
- [x] Optional later (Phase 2): rainfall / humidity / temperature from BMD, used only as data known at the origin.

### Day 6 — Baselines & preprocessing (`06_baselines.py`)
- [x] Baselines: Persistence (last day), 7-day mean, same weekday last week, 7-day trend (drift).
- [x] Metrics (`src/evaluation.py`): **MAE (primary)**, RMSE, R², bias, MASE vs persistence, mean Poisson deviance,
      80% interval coverage. Pooled and per-unit averages, for district and division level.
- [x] Target modes compared: raw count, `log1p(count)`, and log-ratio to the 7-day mean (the dengue counterpart of
      TFS's climatology anomaly). Preprocessing profiles reused from TFS (impute / clip / scale / encode).

### Day 7 — Model screening (`07_screen.py`, resumable)
- [x] Candidates (count-appropriate subset of the TFS 17): Ridge, Lasso, ElasticNet, Huber, PoissonRegressor,
      TweedieRegressor, RandomForest, ExtraTrees, GradientBoosting, HistGradientBoosting (Poisson loss),
      LightGBM (Poisson/Tweedie), XGBoost (count:poisson), CatBoost (Poisson), KNN, MLP.
- [x] 7 horizons × 2 levels × models × profiles × CV folds. About 100k rows per horizon (65 units × ~1,500 origins), so
      much faster than TFS (minutes to 1–2 h, not 4 h).

### Day 8 — Tuning (`08_tune.py`, Optuna, resumable)
- [x] Top-N models per horizon and level, 50 trials or a time cap per study (TFS settings).

### Day 9 — Final evaluation (`09_evaluate.py`)
- [x] Refit on all development data. The test period is used **once** and logged (`results/09_test_access_log.json`).
- [x] Deploy the ML model per horizon only if it beats the best baseline on CV **and** test; otherwise deploy the baseline.
- [x] 80% intervals from CV out-of-fold errors (per horizon, scaled by the forecast level). Report test coverage.
- [x] Per-district and per-division test metrics, high-season vs low-season, permutation importance.

### Day 10 — Audit, forecast engine & web app
- [x] `src/forecasting.ForecastEngine`: Day 1–7 for any unit or all units, error codes, warnings (stale data, missing
      recent days, unit not eligible), JSON/CSV.
- [x] `src/audit.py` checks (adapted from the 13 TFS checks) → `results/audit_report.json`; master report.
- [x] Flask app (`app/`, adapted from TFS `app/`):

| Page | URL | Dengue version |
|---|---|---|
| Dashboard | `/` | units forecastable, data period + latest report date and age, deployed model per horizon, test MAE; leaderboard (baseline vs ML) per horizon; MAE-by-horizon chart; data coverage per district; data-quality summary; figures gallery; downloads |
| Make Forecast | `/forecast` | **Level** (Division / District / Upazila) + cascading **Division → District → Upazila** selectors; **horizon Day 1…7** or **7-day outlook** (default); predicted admissions, 80% range, target date, model, test MAE vs baseline, warnings; chart of last 60 days + forecast band; **All districts / All divisions** table (one or all horizons); JSON/CSV; deep links `/forecast?level=district&unit=…&outlook=1` |
| Model Performance | `/model-performance` | per unit and level: MAE, RMSE, R², bias, skill vs baseline, coverage by horizon; feature importance (plain-language labels); residuals; model info |
| Upload Data | `/data-upload` | upload **DGHS daily PDF(s)** (parsed automatically) or CSV/XLSX → preview → validation (Day 2 rules) → confirmed apply → run mode `data` / `refresh` / `full` with stage progress, cancel, version history and restore |

- [x] API as in TFS, with "station" → "unit": `/api/dashboard-data`, `/api/units?level=`, `/api/forecast`,
      `/api/outlook`, `/api/forecast-all`, `/api/model-metrics`, `/api/upload`, `/api/data-status`,
      `/api/apply-data`, `/api/pipeline-run[/start|/cancel]`, `/api/data-versions/restore`, `/api/downloads`,
      `/api/download/<f>`, `/api/figures`, `/api/status`.
- [x] Same look: TFS `base.html` / `style.css`, local Plotly, light/dark, mobile menu. One addition: a district
      choropleth of the Day-1 forecast (boundaries from `bd-health-signals/data/reference/boundaries_district.geojson`).
- [x] App tests (TFS has 20), browser check desktop/mobile/dark, `USER_MANUAL.md`, `run_app.bat`.

## 6. Tests & acceptance

1. Parser fixtures from hand-checked days match exactly. Reconciliation district → division → national passes.
2. Every eligible district and division returns 7 correctly dated forecasts (Day 4 and Day 6 tested explicitly),
   or a clear reason why not. No negative forecasts or ranges.
3. No leakage (shift test, test-period fingerprint), test set accessed once.
4. Every horizon reports the baseline comparison. Metrics can be reproduced from the saved test predictions.
5. Upload → apply → run → restore keeps the last good state if anything fails.
6. A new session (Claude Code, Codex, or another LLM) can continue from `CLAUDE.md` + `docs/PROGRESS_LOG.md` alone.

## 7. Continuation log (how any session or LLM resumes)

- `CLAUDE.md`: always-current context (commands, conventions, data facts, decisions, stage status), like TFS.
- `AGENTS.md`: tells Codex and other LLMs to read `CLAUDE.md` then `docs/PROGRESS_LOG.md`.
- `docs/PROGRESS_LOG.md`: **append one entry per session**: date, agent, what was done, files changed, commands and
  checks run with results, open problems, **exact next step**. The "Current status" block at the top stays current.
- `pipeline/logs/pipeline_runs/`: machine logs of every pipeline run (as TFS). Long jobs are logged before they start and
  after each stage, with how to check or stop them.
- The boxes in this plan are ticked as stages finish.

## 8. Risks & open questions

| # | Issue | Plan |
|---|---|---|
| 1 | **No district PDFs after 2026-09-03** | Train/test on 2022 → 2026-09-03. The app forecasts from the latest data with the TFS stale-data warning. The Upload page accepts new DGHS PDFs/CSV; `--update` downloader retries daily. **Shihab: can you find where DGHS posts daily district figures now?** |
| 2 | PDF layout changes across years | Detect tables by header text, version the parser, test fixtures per year |
| 3 | Mangled Bangla district names | Alias table + blocking error for any unmapped name |
| 4 | Hospital-location basis (e.g. patients referred to Dhaka) | Label clearly. It is what DGHS reports |
| 5 | Upazila | Not public. Needs DGHS DHIS2/IEDCR access. The architecture supports adding it later |
| 6 | 2023 record outbreak dominates training | Log-scale targets, per-season EDA, report test by season |
| 7 | 2019 PDFs (158, other format), 2020–21 missing | Skipped in v1. Possible later backfill |

## 9. Rough effort

Stage 0 + Days 1–3: 2–3 sessions (the parser is the main work). Days 4–9: 3–4 sessions (compute is small).
Day 10 app: 2–3 sessions (much of it adapted from TFS). **About 8–10 sessions in total.**

## 10. Changes made during implementation (2026-10-12)

- **Second source added**: the DGHS dashboard (dated POST) gives divisions, Bangladesh and DNCC+DSCC (= Dhaka Metro)
  for every day up to today, while the district PDFs stop on 2026-09-03. Division, national and Dhaka Metro
  forecasts are therefore current; other districts use the **top-down** method (division forecast × district share)
  when their own data is stale, with accuracy taken from a backtest at the same data age.
- **National level** added (Bangladesh), so there are 3 levels: national, division, district.
- **Upazila**: Dhaka city thanas map to the Dhaka Metro unit, other upazilas to their district.
- **Target mode** `log_ratio` (log of admissions relative to the 7-day mean) chosen by the Day 6 check.
- **Tuning budget** reduced to 20 trials / 120 s per study, and screening/tuning helpers run levels in parallel.
- **Extra app mode** `update` (download new PDFs + dashboard days, rebuild data) and a Project Log page.
