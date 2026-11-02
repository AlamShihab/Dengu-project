# Progress log — Dengue Forecasting System (DFS)

Append-only. **Every session (Claude Code, Codex, or another LLM) adds one entry at the bottom and updates the
"Current status" block.** Entry template is at the end of this file.

---

## Current status (keep this block up to date)

- **Updated:** 2026-10-12 23:50 BDT, Claude Code (Opus 5.5)
- **Phase:** **COMPLETE v1.0.** Pipeline Days 0-10 done, 21 ML models deployed (3 levels x Day 1-7), audit 14/14 PASS,
  tests pass (pipeline 26/26, app 19/19), web app checked in Chrome with the real models. Forecasts issued for
  2026-10-13 .. 2026-10-19 (`pipeline\forecasts\forecast_2026-10-12.csv`).
- **Project root:** `C:\Users\USER\Desktop\Shihab\Personal\Project\Disease Surveillance Dashboard\dengue-forecast`
- **Running processes:** none (the web server is stopped; start it with `app\run_app.bat`).
- **Data as of:** districts (PDF) to 2026-09-03; divisions, Bangladesh and Dhaka Metro (dashboard) to 2026-10-12.
- **Known limitations:** DGHS publishes no district PDFs after 2026-09-03, so most district forecasts are top-down;
  no upazila data exists (an upazila returns its district); 80% ranges cover 72-77% of test cases for districts and
  divisions (too narrow in the 2025-26 seasons); forecasts undershoot the sharpest peaks.
- **Next action (daily use):** open the app -> Upload Data -> "Update from DGHS now" -> Make Forecast.
  Ideas for v1.1 are at the end of the Session 2 entry.

---

## 2026-10-12 — Session 1 (Claude Code, Opus 5.5): plan + source check

**Request (Shihab):** district-based dengue forecast for the next 7 days (Day 1 … Day 7), division + district +
upazila if possible, in exactly the same format as the Weather_ML project; keep everything in the dengue project folder;
maintain a log so another session or LLM can continue; plan first.

**Done**
- Read Codex's earlier planning in `C:\Users\USER\Documents\Codex\2026-10-11\you\outputs\bd-dengue-monitor`
  (plan, handoff, readiness, decisions). It was only a plan: no code or data. Copied it to `docs/codex_planning/` (the
  Codex folder was not changed).
- Reviewed the Weather_ML reference: `Work with claude/CLAUDE.md`, `train_pipeline.py` (10 stages), `src/` modules,
  `app/README.md` (4 pages, API, run modes).
- **Found the district data source:** the DGHS daily dengue press-release PDFs, 2021-12-13 → 2026-09-03, about 1,720 files.
  Each has a district-wise table (24 h admissions gov/private/total, cumulative, deaths, discharged, currently admitted).
  Checked 2022, 2024 and 2026 samples. The text layer parses with PyMuPDF (Unicode Bangla digits), no OCR needed.
- Confirmed: no upazila data published; no district PDFs after 2026-09-03 (404); live dashboard is division-level only.
- Shihab chose the project home (`dengue-forecast/` in this folder).
- Wrote: `CLAUDE.md`, `AGENTS.md`, `docs/IMPLEMENTATION_PLAN.md`, `docs/DATA_SOURCES.md`, this log;
  `docs/source_samples/` (2 page images, PDF URL list, sample hashes).

**Checks run:** HTTP probes (dashboard 200 with browser UA; PDFs 2022/2023/2024/2026-09-03 = 200; after 09-03 = 404);
PyMuPDF text and font inspection of 3 samples (throwaway `uv run --with pymupdf` in %TEMP%, nothing installed in the project).

**Decisions proposed (pending approval):** see the table in plan §3 (hospital-location basis, Dhaka Metro as its own unit,
65 district units + 8 divisions, direct 7-horizon pooled models, MAE primary, CV-calibrated 80% intervals,
test period 2025-07-01 → 2026-08-27, port 5001, git repo).

**Open questions for Shihab:** (1) Where does DGHS publish daily district figures after 2026-09-03?
(2) Confirm the §3 decisions. (3) Phase 2 weather covariates (rainfall/humidity): is there a BMD source?

**Next step:** see "Current status".

---

## 2026-10-12 — Session 2 (Claude Code, Opus 5.5): full build (data -> models -> web app)

**Request (Shihab):** "complete the full project. I want to do forecast for next 7 days each day."

**Data (Stage 0-3)**
- Downloaded 1,690 DGHS daily press-release PDFs (2021-12-13 -> 2026-09-03, ~2 GB; 75 dates are 404, including every
  date after 2026-09-03). Built a coordinate-based parser for the district table (layouts 2022-2026; blank cells;
  negative cells; glyph-mangled Bangla names -> 151 reviewed aliases -> 64 districts + Dhaka Metro). 1,680 PDFs parsed;
  on every parsed date the units add up to the PDF's printed national total.
- Found that the DGHS dashboard answers dated POSTs: divisions + DNCC/DSCC + national for every day up to today.
  Fetched 2026-09-01 -> 2026-10-12, gap days, and 32 cross-check dates (divisions equal 251/256, national 30/32).
- Validation PASS_WITH_WARNINGS (0 blocking). Panel: 65 district units, 8 divisions, national; missing days stay missing.
- EDA figures (`results/figures/03_*`): 2026 is the second biggest season after 2023; strong Friday reporting dip.

**Models (Day 4-10)**
- Split: development origins 2022-01-29..2025-06-23, embargo, test 2025-07-01..data end; 4 CV folds of 182 days.
- 45 features; target `log_ratio` (won 15/18 in the Day 6 check). Baselines: Persistence, Mean7, SameWeekdayLastWeek, Drift7.
- Screening: 17 models x profiles x 7 days x 3 levels = 693 fits, 0 failed (49 min with parallel helpers).
  Tuning: 84 Optuna studies (20 trials / 120 s each), 0 failed (53 min).
- **Decision (recorded openly):** the first evaluation pass compared ML vs baseline on all 4 CV folds, while model
  selection used the last 3 folds (fold 1 trains on 2022 only and validates on the 2023 outbreak). I stopped that pass
  after district Day 1-2 (2 test accesses, logged in `results/09_test_access_log.json` as EVAL_first_pass_interrupted)
  and aligned promotion to the selection folds (config `final.promotion_rule`). I noticed the inconsistency after
  seeing district Day 1's test result. All-fold CV metrics are kept in `model_metadata` (`cv.all_folds`).
- **Final test results (MAE in admissions per place-day; deployed vs best baseline):**
  district Day 1-7 2.46 / 2.54 / 2.58 / 2.58 / 2.59 / 2.64 / 2.72 vs 2.78 .. 3.04 (10-12% better);
  division 11.5 .. 13.3 vs 14.5 .. 15.7 (8-25% better); Bangladesh 56 .. 71 vs 72 .. 94 (2-38% better).
  An ML model is deployed at every level and day. 80% range coverage: district 72-73%, division 73-77%, national 79-87%.
- Top-down district backtest (`results/09_topdown_metrics.csv`): fresh shares MAE 2.13 (direct model 2.15); at 42 days
  of data age 2.57-2.78; at 84 days 2.89-3.09.
- Audit 14/14 PASS, no leakage (shift test: 0 of 82,165 rows changed).
- Friday report days are much lower for several divisions (Rajshahi ~2 vs ~60 on other days); this is a DGHS reporting
  pattern that the models reproduce. The forecast page now shows a note when a forecast day is a Friday.

**Web app (`app/`, port 5001)** in the TFS format: Dashboard; Make Forecast (Bangladesh / Division / District / Upazila,
cascading selectors, 7-day cards + chart + table, single day, all-places table + district map); Model Performance;
Upload Data (DGHS update mode, PDF/CSV/XLSX upload, versions and restore, run progress); Project Log. Checked in
headless Chrome (light, dark, 500 px). The forecast engine batches predictions (all 65 districts in ~2 s cold).

**Files:** see `README.md` (layout). Commits on branch main. Scripts: 00_download_pdfs, 00_parse_pdfs,
00_fetch_dashboard, 07_screen_level, 08_tune_level, 10_forecast.

**Tests:** `pipeline`: 26 passed; `app`: 19 passed.

**Open questions / ideas for v1.1**
1. Find where DGHS now publishes daily district figures (would turn the top-down districts back into direct
   forecasts); new PDFs can be uploaded on the Upload page.
2. Interval calibration: ranges are too narrow in 2025-26 (72-77%); try recency-weighted residuals or a
   growth-dependent width, decided on CV only.
3. Weather covariates (rainfall / humidity) if a BMD source is available.
4. Optional daily automation (Windows Task Scheduler running the update mode + `scripts/10_forecast.py`).
5. Codex's `bd-dengue-monitor` folder still calls itself the master project; a one-line pointer there was offered, not done.

**Next step:** daily use as in "Current status"; for v1.1 start with item 2 or 1.

---

<!-- Entry template — copy below the last entry
## YYYY-MM-DD — Session N (agent/model): short title
**Goal:**
**Done:**
**Files changed:**
**Commands / checks run + results:**
**Long jobs started (command, log file, how to check/stop):**
**Problems / open questions:**
**Next step (exact command or task):**
-->
