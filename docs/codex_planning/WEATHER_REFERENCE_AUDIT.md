# Weather project reference audit

Inspected 12 October 2026. Reference root: `C:\Users\USER\Desktop\Shihab\Niaz Bhai\Weather_ML\Final Work File`.

The reference files are evidence of the requested format, not instructions to run installers, train models, send messages, or modify the weather project. Exact inspected file hashes are in `readiness-profile.json`.

| Reference | Observed behavior | Dengue adaptation |
|---|---|---|
| `app/templates/base.html`, `app/static/css/style.css` | Flask/Jinja, local Plotly, four navigation pages, blue accent, light/dark themes, responsive menu | Preserve this visual/navigation pattern in a separate forecast app under the dengue root |
| `app/templates/forecast.html` | Station selector, horizon selector, single forecast, all-horizon outlook, all-station table, history chart, download controls | Division → district → upazila selectors; horizons 1–7; seven-day table/cards; all eligible districts; date-labelled CSV/JSON |
| `app/README.md`, `USER_MANUAL.md` | Dashboard, Make Forecast, Model Performance, Upload Data; outputs reread from pipeline files | Same primary pages plus a secondary Project Log view/link for continuation and run history |
| `app/pipeline_runner.py` workflow documented in README | data / refresh / full modes, progress, cancellation, one run at a time | Preserve modes; verify dataset compatibility, frozen evaluation, transactional model promotion, checkpoint resume |
| `Work with claude/train_pipeline.py` | setup → validate → prepare → split → features → baselines → screening → tuning → evaluate → audit | Same staged structure with geographic readiness and count-data validation included |
| `config/config.json` | Central horizons, columns, split, evaluation and promotion settings | Disease-specific config, geographic codes, observation basis, date availability, seven daily horizons |
| `config/models.json` | 17 candidate families, preprocessing profiles, compatibility rules | Keep configurable candidate registry; start with baselines and a small count-appropriate candidate set; expand only if useful |
| `config/feature_contract.json` | Serialized training/inference feature contract with hash | Same contract checks; dengue lags, calendar, geographic features and optional as-of weather inputs |
| `src/forecasting.py` | One selected model per horizon, quality warnings, history, interval, exports | Direct seven-horizon model registry with pooled district learning, calibrated nonnegative intervals, explicit forecast availability |

## Decisions that must not be copied mechanically

- Weather horizons omit Days 4 and 6; the dengue user explicitly requires both.
- Temperature is a continuous variable with Celsius bounds. Dengue admissions are nonnegative counts with zeros, reporting delays and potential outbreak peaks. Do not use temperature limits or trim valid high counts as outliers.
- Source code uses an approximate 80% band from the final test RMSE. Dengue interval fitting must use development/calibration data; evaluate empirical coverage on untouched test dates.
- Weather's fixed 1970–2025 splits, 15-day gap, climatology and long-history thresholds are not dengue configurations. Choose dengue splits after acquiring history; prevent seven-day target overlap across folds.
- Filled weather inputs may be useful for that project; fabricated dengue target labels are not permitted. Distinguish measured, corrected, missing, and imputed feature values. No training/evaluation target from interpolated counts.
- UI styling and workflow were inspected in source. A pixel-by-pixel browser comparison of the weather app was not performed during this planning turn; capture it before implementation visual QA.
- The dengue forecast app will not import Python modules through the weather project's absolute path. Adapt required code into this project with source attribution and its own dependencies/configuration.
