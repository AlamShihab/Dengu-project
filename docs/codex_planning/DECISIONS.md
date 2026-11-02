# Decision register

## 2026-10-12 — geographic seven-day dengue forecasting

- **User requirement:** Day 1 through Day 7 forecasts; district priority, division support, upazila if possible; match the supplied Weather_ML format; keep all work and continuation logs inside the dengue project; plan before implementation.
- **Active direction:** Forecasting supersedes the proposed claim-checker extension. Existing monitoring V1 remains useful input/evidence infrastructure.
- **Continuation root:** Existing `outputs/bd-dengue-monitor` project. Separate Desktop bd-health-signals and Weather_ML remain references. No migration/deletion performed.
- **Format interpretation:** Reuse the actual weather Flask app's navigation, visual style, forecast controls, performance/upload pages, downloads and staged file-based pipeline. Preserve current React monitoring runtime by adding the forecast app in its own subfolder.
- **Proposed target:** Daily reported dengue hospital admissions with explicit facility-based geography where dictated by source. This is not a claim about all infections or resident-level risk.
- **Geographic gate:** District history must be acquired/validated first. Upazilas are enabled only where observed daily history and validation support forecasts; no population allocation masquerading as observed dengue data.
- **Model plan:** Seven direct pooled geographic horizon models and simple baselines; configurable registry. Temperature weights, fixed splits and test-RMSE interval formula are not reused.
- **Status:** F00 planning completed. F01 source/geography audit is the next step. No new model training or forecast UI implementation in this session.
