# Dengue Forecasting System: user manual

## 1. Start the app

Double-click `app\run_app.bat`. A browser opens at **http://127.0.0.1:5001**. Keep the black window open while you
use the app, and close it to stop.

## 2. Get today's data first (once a day)

Go to **Upload Data**, then **Update from DGHS now**. The app downloads any new DGHS daily reports and the dashboard's
division and Bangladesh figures up to today, then rebuilds the data (a few minutes, needs the internet). The forecasts
then start from the newest day.

## 3. Make a forecast

Go to **Make Forecast**:

1. Choose the **level**: Bangladesh, Division, District or Upazila.
2. Choose the **division**, then the **district**, then the **upazila** (when that level is chosen).
3. Press **Show 7-day forecast**.

You get seven cards, Day 1 to Day 7, each with the date, the forecast number of dengue hospital admissions and its
**80% range**. Roughly 8 days in 10 the real number falls inside the range. Below the cards are a chart of the last
60 days with the forecast, and a table with the model used and its average error (test MAE). Use the buttons to
download the forecast as CSV or JSON.

* **Forecast the selected day only**: pick a day with the slider (Day 1 to Day 7).
* **All districts: 7-day table + map**: every district's 7-day forecast in one table (busiest first) and a map for the
  selected day. In Division level the button shows all divisions.

### Reading the labels

* **direct**: the forecast uses the place's own latest data.
* **top-down**: DGHS stopped publishing district figures after 3 Sep 2026 but still publishes division figures. A
  district forecast is then the division forecast × that district's usual share of the division. It is current, but
  less precise for single districts. The error shown is from a backtest at the same data age.
* **Upazila**: DGHS publishes no upazila dengue data, so an upazila shows its district's forecast, with a note. Dhaka
  city thanas (Mirpur, Dhanmondi, ...) show the Dhaka Metropolitan (city hospitals) forecast.
* **Dhaka Metropolitan (city hospitals)** and **Dhaka (outside metropolitan)** are separate units, because DGHS
  reports them separately. Dhaka division includes both.
* Counts are **hospital admissions by hospital location** (where patients were admitted), not all infections.

### Fridays

Friday is the weekly holiday. Many hospitals report few or no admissions on Friday reports, and those patients appear
in the Saturday and Sunday reports. Rajshahi division, for example, reports ~2 admissions on Fridays against ~60 on
other days. The forecasts reproduce this **reporting** pattern, so a Friday forecast is much lower. Look at the 7-day
total, or at the days around it, for the real trend.

### Warnings

* *The latest data is from ... days ago*: the forecasts are for dates that have already passed. Run the DGHS update
  or upload newer reports.
* *Only N of the last 7 days were reported*: some recent reports are missing, so the forecast is less certain.

## 4. How good are the forecasts?

**Dashboard** shows, for each forecast day, the error of the deployed model and of the best simple rule (baseline, for
example "average of the last 7 days") on a test period the models never saw (July 2025 onwards). A machine-learning
model is used only if it beats the baseline. **Model Performance** shows the same for any division or district, plus
which inputs matter most.

## 5. Add data yourself

On **Upload Data**, drop either:

* a **DGHS daily PDF** (e.g. `20261012_dengue_all.pdf` from the DGHS website), or
* a **CSV/Excel table** with columns `report_date` (YYYY-MM-DD), `district` (or `division`, or `unit_code`) and
  `admitted_24h`.

Press **Check File**, read the preview, choose how much to re-compute (normally **Update the data only**) and press
**Add data & run pipeline**. Every change is saved as a version first. **Restore** in the version history undoes it.

## 6. Re-training

* **Rebuild and refit models** (minutes): refits the chosen models on all data.
* **Full re-analysis** (hours): repeats model screening and tuning from scratch.

## 7. Where everything is

* Project status and the work log: **Project Log** page, or `docs\PROGRESS_LOG.md`.
* Results files: Dashboard → *Download Results*, or `pipeline\results\`.
* Technical details: `README.md` (project), `app\README.md` (web app), `CLAUDE.md` (for developers and AI assistants).
