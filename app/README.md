# DFS Web Application (Flask)

Web front end of the **Dengue Forecasting System**. It has the same layout, pages, API style and run modes as the
TFS weather app (`Weather_ML/Final Work File/app`). It forecasts **daily dengue hospital admissions for Day 1 to Day 7**
for Bangladesh, its 8 divisions and its 64 districts (+ Dhaka Metropolitan city hospitals as their own unit). An
upazila selection returns its district's forecast, clearly labelled, because DGHS publishes no upazila data.

The app has no database. It reads the pipeline's outputs (`../pipeline/results`, `models`, `model_metadata`,
`predictions`, `data/processed`) and reuses the pipeline's own code (`src.forecasting.ForecastEngine`, the PDF parser,
validation), so forecasts use exactly the same features and models as training.

## Setup

The app runs in the pipeline's virtual environment (Python 3.12, created with uv):

```powershell
cd ..\pipeline
uv venv .venv --python 3.12
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
```

## Run

Double-click **`run_app.bat`** (or `run_app.ps1`). It opens **http://127.0.0.1:5001**. Or, from this folder:

```powershell
..\pipeline\.venv\Scripts\python.exe app.py
```

Port 5001 avoids the TFS weather app on 5000. If the port is taken, the app stops with a message.

### Configuration (environment variables or a `.env` file here)

| Variable | Default | Meaning |
|---|---|---|
| `DFS_PROJECT_DIR` | `..\pipeline` | folder with `results\`, `models\`, `data\`, `config\` |
| `DFS_CODE_DIR` | `..\pipeline` | folder with the `src` package and `train_pipeline.py` |
| `DFS_PORT` / `DFS_HOST` | `5001` / `127.0.0.1` | where the server listens |
| `DFS_MAX_UPLOAD_MB` | `25` | upload size limit |
| `DFS_DEBUG` | `0` | `1` = Flask debug mode (development only) |
| `DFS_TODAY` | today (Dhaka) | pretend "today" (testing only) |

## Pages

| Page | URL | What it shows |
|---|---|---|
| Dashboard | `/` | places forecast, district test MAE, latest data dates, deployed models and audit status; leaderboard per level (Districts / Divisions / Bangladesh) and forecast day (best baseline vs ML model, improvement, what is deployed, 80% range coverage); MAE-by-day chart; data coverage per district; data-quality cards; pipeline figures; result downloads |
| Make Forecast | `/forecast` | **Level** (Bangladesh / Division / District / Upazila) with **Division → District → Upazila** selectors. **Show 7-day forecast** (default): Day 1 to Day 7 cards with date, forecast admissions and 80% range, the 7-day total, a chart of the last 60 days plus the forecast band, a table with model and test MAE, and JSON/CSV downloads. **Forecast the selected day only**: one day with the model metrics. **All districts / all divisions**: a 7-day table for every place (sorted by total, CSV) and a **district map** of the selected day. Deep links: `/forecast?unit=BD3029&outlook=1`, `/forecast?unit=BD30&horizon=4`, `/forecast?level=district&all=1` |
| Model Performance | `/model-performance` | per level, place and day: MAE, RMSE, bias, R², 80% coverage vs the best baseline; MAE chart (place vs all places vs baseline); actual vs forecast over the test period; feature importance with plain-language names; error histogram; model information; top-down backtest by district data age |
| Upload Data | `/data-upload` | **Update from DGHS now** (downloads new PDFs and dashboard days, then rebuilds the data). **Upload** a DGHS daily PDF (read by the pipeline's parser) or a CSV/XLSX table (`report_date`, `unit_code` or `district`/`division`, `admitted_24h`), then check it and preview it. **Add data & run** is a separate step with a choice of run mode, a version snapshot first, and automatic restore if the run fails. Also shows run progress, cancel, data status and version history with restore |
| Project Log | `/project-log` | the continuation log `docs/PROGRESS_LOG.md`, pipeline runs and web-app runs |

## How forecasts are made

* **Direct**: the place's own latest data feeds the deployed model for each day ahead (one model per level and day,
  pooled over all places of the level). Used for Bangladesh, the divisions, Dhaka Metropolitan, and districts with
  current data.
* **Top-down**: DGHS stopped publishing the district table after 3 Sep 2026, but still publishes division figures
  on its dashboard. A district whose data is stale while its division is current gets the division forecast
  (Dhaka: minus the Dhaka Metro forecast) × the district's share of its division in its last 28 reported days.
  Accuracy and ranges come from the Day 9 backtest at the same data age (`results/09_topdown_metrics.csv`).
* **80% range**: quantiles of out-of-fold log errors from cross-validation, by forecast size, never fitted on the
  test period. The coverage achieved on the test period is shown on the dashboard.
* Forecasts are for **report dates**. DGHS report day D covers the 24 hours ending 8 am on D. Counts are by
  **hospital location**, not patient residence.

## API

| Method | Route | Body / params | Returns |
|---|---|---|---|
| GET | `/api/status` | – | configuration check, horizons, levels, which result files exist |
| GET | `/api/dashboard-data` | – | KPIs, leaderboards per level, coverage, data quality, audit, messages |
| GET | `/api/locations` | – | division → district → upazila hierarchy with last data dates |
| GET | `/api/units?level=district` | – | places of a level |
| POST | `/api/outlook` | `{"unit": "BD3029"}` | Day 1-7 forecasts (date, predicted, lower_80, upper_80, model, method, test MAE), warnings, 60-day history |
| POST | `/api/forecast` | `{"unit": "BD30", "horizon": 4}` | one day (same fields) |
| POST | `/api/forecast-all` | `{"level": "district"}` (+ `"horizon"`) | every place of the level; `skipped` with reasons |
| POST | `/api/map` | `{"horizon": 1}` | district forecasts + district boundaries (GeoJSON) |
| POST | `/api/model-metrics` | `{"level", "unit", "horizon"}` | metrics by day, importance, residuals, actual vs forecast, model info, top-down backtest |
| POST | `/api/upload` | multipart `file` (.pdf/.csv/.xlsx) | check result and preview (saved, not applied) |
| POST | `/api/apply-data` | `{"file": "<saved_as>", "mode": "data"\|"refresh"\|"full"}` | snapshot + add data + start a run |
| GET | `/api/data-status` | – | PDFs, dashboard, uploads, versions, run modes, current run |
| GET | `/api/pipeline-run` | – | progress of the current/last run |
| POST | `/api/pipeline-run/start` | `{"mode": "update"\|"data"\|"refresh"\|"full"}` | starts a run |
| POST | `/api/pipeline-run/cancel` | – | stops the running stage |
| POST | `/api/data-versions/restore` | `{"id": "v0001_..."}` | restores a data version and rebuilds the data |
| GET | `/api/downloads`, `/api/download/<file>` | – | result files (`.json/.csv/.md` in `results\` only) |
| GET | `/api/figures`, `/figures/<name>` | – | pipeline PNG figures |
| GET | `/api/project-log` | – | progress log markdown and run history |

Errors are JSON `{"status": "error", "code": ..., "message": ...}`, with no stack traces.

## Run modes

| Mode | Stages | When |
|---|---|---|
| `update` | download new PDFs → fetch dashboard → ingest → setup → validate → prepare | daily: brings the data to today; forecasts move forward immediately (needs internet) |
| `data` | ingest → setup → validate → prepare | after uploading files |
| `refresh` | data stages → split → features → baselines → evaluate → audit | refit the deployed model families on the new data (minutes) |
| `full` | everything incl. screening and tuning (old results archived, never deleted) | re-analysis (hours) |

## Where the numbers come from

| Shown | Pipeline file |
|---|---|
| Leaderboards, test period, deployed models | `results/09_final_evaluation.json` (before Day 9: `06_baseline_results.json`) |
| Place metrics | `results/09_unit_metrics.csv` |
| Actual vs forecast, residuals | `predictions/09_test_predictions.parquet` |
| Feature importance | `results/09_importance_<level>_h<h>.csv` |
| Model information, intervals | `model_metadata/best_<level>_<h>d.json` |
| Top-down accuracy | `results/09_topdown_metrics.csv` |
| Coverage | `results/02_unit_eligibility.csv`; data quality: `results/01_validation_report.json` |
| Audit | `results/audit_report.json` |
| Forecasts | `src.forecasting.ForecastEngine` + `models/current/best_<level>_<h>d.joblib` + `data/processed/02_daily_panel.parquet` |

## Differences from the TFS app (and why)

* Horizons are **Day 1 to Day 7, every day** (TFS: 1, 2, 3, 5, 7, 10, 13, 15).
* Places are hierarchical (Bangladesh / division / district / upazila) instead of a station list, with a district map.
* Error is **MAE in admissions** (counts are skewed; TFS used RMSE in °C). The 80% range comes from CV residual
  quantiles, not ±1.28 × test RMSE.
* Uploads accept the DGHS **PDF** itself, and there is an automatic **update** mode, because new data arrives daily.
* An extra **Project Log** page shows the continuation log.

## Tests

```powershell
..\pipeline\.venv\Scripts\python.exe -m pytest        # in this folder (uses the real pipeline folder, read-only)
```

## Security notes

The app binds to 127.0.0.1 by default. Uploads are size-limited, stored under generated names in
`static/uploads`, and are never applied without a second request. Downloads are limited to `.json/.csv/.md` files
directly in `results/`.
