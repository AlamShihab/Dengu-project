"""Dengue Forecasting System (DFS) - Flask web application (same design as the TFS weather app).

    python app.py            ->  http://127.0.0.1:5001

Reads the pipeline outputs from ``config.PROJECT_DIR`` (no database) and reuses the pipeline's own code
for forecasting (``src.forecasting.ForecastEngine``), PDF parsing and validation, so the website applies
exactly the same features, models and rules as the training pipeline.

Pages:  /  /forecast  /model-performance  /data-upload  /project-log
API:    /api/dashboard-data  /api/locations  /api/units  /api/forecast  /api/outlook  /api/forecast-all
        /api/map  /api/model-metrics  /api/upload  /api/apply-data  /api/data-status  /api/pipeline-run
        /api/pipeline-run/start  /api/pipeline-run/cancel  /api/data-versions/restore  /api/downloads
        /api/download/<file>  /api/figures  /api/project-log  /api/status
"""
from __future__ import annotations

import io
import json
import logging
import math
import os
import re
import socket
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from flask import Flask, jsonify, render_template, request, send_from_directory
from werkzeug.exceptions import HTTPException
from werkzeug.utils import secure_filename

import config

if str(config.CODE_DIR) not in sys.path:
    sys.path.append(str(config.CODE_DIR))   # after the app folder

import data_versions  # noqa: E402
from pipeline_runner import mode_options, runner  # noqa: E402

app = Flask(__name__)
app.config.update(UPLOAD_FOLDER=str(config.UPLOAD_FOLDER), MAX_CONTENT_LENGTH=config.MAX_FILE_SIZE,
                  SECRET_KEY=config.SECRET_KEY, TESTING=config.TESTING, JSON_SORT_KEYS=False)
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")
logger = logging.getLogger("dfs.webapp")

# =============================================================================
# Pipeline access (cached, reloaded when files change)
# =============================================================================
_lock = threading.Lock()
_file_cache: Dict[str, tuple] = {}
_pipeline: Dict[str, Any] = {}


def _mtime(path: Path) -> Optional[float]:
    try:
        return path.stat().st_mtime
    except OSError:
        return None


def get_settings():
    cfg = config.PROJECT_DIR / "config" / "config.json"
    key = ("settings", _mtime(cfg), _mtime(config.PROJECT_DIR / "config" / "geography.json"))
    with _lock:
        if _pipeline.get("settings_key") != key:
            from src.config import load_settings
            from src.paths import ProjectPaths
            _pipeline["settings"] = load_settings(ProjectPaths(root=config.PROJECT_DIR))
            _pipeline["settings_key"] = key
        return _pipeline["settings"]


def get_engine():
    s = get_settings()
    meta = sorted((config.MODEL_METADATA_DIR).glob("best_*d.json")) if config.MODEL_METADATA_DIR.exists() else []
    key = (_mtime(s.paths.processed / "02_daily_panel.parquet"), tuple(_mtime(m) for m in meta),
           datetime.now().date().isoformat())
    with _lock:
        if _pipeline.get("engine_key") != key:
            from src.forecasting import ForecastEngine
            logger.info("Loading forecast engine (data and models)")
            _pipeline["engine"] = ForecastEngine(s)
            _pipeline["engine_key"] = key
        return _pipeline["engine"]


def _clear_caches(_state=None) -> None:
    with _lock:
        _pipeline.clear()
    _file_cache.clear()


runner.on_finish = _clear_caches


def load_json_results(filename: str) -> Optional[dict]:
    path = config.RESULTS_DIR / filename
    mt = _mtime(path)
    if mt is None:
        return None
    cached = _file_cache.get(str(path))
    if cached and cached[0] == mt:
        return cached[1]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.error("Could not read %s: %s", path, exc)
        return None
    _file_cache[str(path)] = (mt, data)
    return data


def load_csv(filename: str) -> Optional[pd.DataFrame]:
    path = config.RESULTS_DIR / filename
    mt = _mtime(path)
    if mt is None:
        return None
    cached = _file_cache.get(str(path))
    if cached and cached[0] == mt:
        return cached[1]
    try:
        df = pd.read_csv(path)
    except (OSError, ValueError) as exc:
        logger.error("Could not read %s: %s", path, exc)
        return None
    _file_cache[str(path)] = (mt, df)
    return df


def clean(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        v = float(obj)
        return None if math.isnan(v) or math.isinf(v) else v
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (pd.Timestamp, datetime)):
        return obj.strftime("%Y-%m-%d")
    return obj


def api_error(message: str, status: int = 400, code: str = "BAD_REQUEST", **extra):
    return jsonify(clean({"status": "error", "code": code, "message": message, **extra})), status


def dfs_error(exc) -> tuple:
    code = getattr(exc, "code", "ERROR")
    status = 404 if code in ("UNKNOWN_UNIT", "NO_DATA") else 503 if code in ("MODELS_MISSING", "DATA_MISSING") else 400
    return api_error(getattr(exc, "message", str(exc)), status, code)


def pipeline_ready() -> bool:
    return (config.RESULTS_DIR / config.FINAL_EVALUATION_JSON).exists() and any(
        (config.MODELS_DIR / "current").glob("best_*d.joblib"))


def unit_names() -> Dict[str, str]:
    from src.geography import unit_table
    return {u["unit_code"]: u["name"] for u in unit_table(get_settings().geography)}


# =============================================================================
# Dashboard helpers
# =============================================================================
def format_leaderboard(level: str) -> List[Dict[str, Any]]:
    fe = load_json_results(config.FINAL_EVALUATION_JSON)
    rows = []
    if fe and level in fe.get("levels", {}):
        for key, x in fe["levels"][level]["horizons"].items():
            rows.append({"horizon": int(key[1:]), "baseline_name": x["best_baseline"],
                         "baseline_mae": x["test_MAE_best_baseline"], "ml_model": x.get("candidate"),
                         "ml_mae": x.get("test_MAE_ml"), "deployed_model": x["deployed_model"],
                         "deployed_kind": x["deployed_kind"], "deployed_mae": x["test_MAE_deployed"],
                         "deployed_rmse": x["test_RMSE_deployed"],
                         "improvement_percent": x.get("improvement_vs_baseline_pct"),
                         "coverage": x.get("interval_coverage_test"), "status": "final"})
        return sorted(rows, key=lambda r: r["horizon"])
    base = load_json_results(config.BASELINE_RESULTS_JSON)
    if base and level in base.get("levels", {}):
        for key, x in base["levels"][level].items():
            b = x["best_baseline"]
            rows.append({"horizon": int(key[1:]), "baseline_name": b, "baseline_mae": x["cv"][b]["MAE"],
                         "ml_model": None, "ml_mae": None, "deployed_model": None, "deployed_kind": None,
                         "deployed_mae": None, "improvement_percent": None, "coverage": None, "status": "pending"})
    return sorted(rows, key=lambda r: r["horizon"])


def calculate_summary_stats() -> Dict[str, Any]:
    v = load_json_results(config.VALIDATION_JSON) or {}
    prep = load_json_results(config.PREPARATION_JSON) or {}
    audit = load_json_results(config.AUDIT_JSON) or {}
    fe = load_json_results(config.FINAL_EVALUATION_JSON) or {}
    el = load_csv(config.ELIGIBILITY_CSV)
    names = unit_names()
    levels = {lv: format_leaderboard(lv) for lv in ["district", "division", "national"]}
    coverage = []
    if el is not None:
        for r in el[el["level"] == "district"].itertuples():
            total = max(int(r.observed_days) + int(r.missing_days), 1)
            coverage.append({"unit_code": r.unit_code, "name": names.get(r.unit_code, r.unit_code),
                             "observed_pct": round(100 * r.observed_days / total, 2),
                             "missing_pct": round(100 * r.missing_days / total, 2),
                             "last_observed": str(r.last_observed)[:10], "mean_daily": r.mean_daily})
        coverage.sort(key=lambda c: -(c["mean_daily"] or 0))
    period = v.get("period", {})
    lv = prep.get("levels", {})
    messages = []
    if not v:
        messages.append("Validation results not found - run the pipeline.")
    if not pipeline_ready():
        messages.append("The final models are not trained yet - forecasts become available after the final "
                        "evaluation stage. Baseline results are shown where available.")
    deployed = [r for rows in levels.values() for r in rows if r.get("deployed_model")]
    dist_mae = [r["deployed_mae"] for r in levels["district"] if r.get("deployed_mae") is not None]
    return {
        "pipeline_ready": pipeline_ready(),
        "units": {"divisions": lv.get("division", {}).get("units"), "districts": lv.get("district", {}).get("units")},
        "avg_mae_district": float(np.mean(dist_mae)) if dist_mae else None,
        "data_period": {"first": period.get("first_report"), "pdf_last": prep.get("pdf_end"),
                        "dashboard_last": prep.get("dashboard_end"),
                        "district_last": lv.get("district", {}).get("last_observed"),
                        "division_last": lv.get("division", {}).get("last_observed")},
        "test_period": fe.get("test_period"),
        "leaderboards": levels,
        "deployed_models": len(deployed), "ml_models": sum(1 for r in deployed if r["deployed_kind"] == "ml"),
        "coverage": coverage,
        "data_quality": {"reports": period.get("reports"), "parsed_ok": period.get("parsed_ok"),
                         "missing_report_days": period.get("missing_report_days"),
                         "validation_status": v.get("status"), "issue_counts": v.get("issue_counts"),
                         "pdf_vs_dashboard": {k: (v.get("pdf_vs_dashboard") or {}).get(k)
                                              for k in ["overlap_rows", "mismatch_rows"]}},
        "audit": {"pipeline_status": audit.get("pipeline_status"), "passed": audit.get("passed"),
                  "total": audit.get("total"), "data_leakage_detected": audit.get("data_leakage_detected")},
        "messages": messages,
    }


_FEATURE_LABELS = {
    "unit_code": "Place (district / division)", "year": "Year", "origin_dow": "Weekday of the last report",
    "epi_week": "Epi week", "target_dow": "Weekday of the forecast day", "target_month": "Month of the forecast day",
    "target_doy_sin": "Season of the forecast day (sine)", "target_doy_cos": "Season of the forecast day (cosine)",
    "lag_0": "Admissions on the last report day", "base": "Level of the last 7 days (7-day mean)",
    "n_obs_7": "Reported days in the last 7", "miss_share_28": "Share of missing days, last 28",
    "ly_target": "Same time last year (around the forecast day)",
    "ly_change": "Last year's change over the same days",
    "div_roll_mean_7": "Division: 7-day mean", "div_growth_7": "Division: weekly growth",
    "nat_roll_mean_7": "Bangladesh: 7-day mean", "nat_growth_7": "Bangladesh: weekly growth",
}
_FEATURE_PATTERNS = [
    (r"lag_(\d+)", "Admissions {} days before the last report"), (r"roll_mean_(\d+)", "Mean of the last {} days"),
    (r"roll_max_(\d+)", "Highest day in the last {} days"), (r"roll_std_(\d+)", "Variability of the last {} days"),
    (r"growth_(\d+)", "Growth of the {}-day mean"),
]


def feature_label(name: str) -> str:
    if name in _FEATURE_LABELS:
        return _FEATURE_LABELS[name]
    for pattern, text in _FEATURE_PATTERNS:
        m = re.fullmatch(pattern, name)
        if m:
            return text.format(m.group(1))
    return name.replace("_", " ")


# =============================================================================
# Pages
# =============================================================================
@app.route("/")
def dashboard():
    return render_template("dashboard.html", active="dashboard")


@app.route("/forecast")
def forecast_page():
    return render_template("forecast.html", active="forecast")


@app.route("/model-performance")
def model_performance_page():
    return render_template("model_performance.html", active="performance")


@app.route("/data-upload")
def data_upload_page():
    return render_template("data_upload.html", active="upload",
                           max_mb=config.MAX_FILE_SIZE // (1024 * 1024))


@app.route("/project-log")
def project_log_page():
    return render_template("project_log.html", active="log")


# =============================================================================
# API - status, dashboard, places
# =============================================================================
@app.route("/api/status")
def api_status():
    try:
        s = get_settings()
        cfg_ok, cfg_msg = True, None
    except Exception as exc:  # noqa: BLE001
        s, cfg_ok, cfg_msg = None, False, str(getattr(exc, "message", exc))
    return jsonify(clean({"status": "ok", "project_dir": str(config.PROJECT_DIR), "config_ok": cfg_ok,
                          "config_error": cfg_msg, "pipeline_ready": pipeline_ready(),
                          "horizons": list(s.horizons) if s else [], "levels": list(s.levels) if s else [],
                          "files": {f: (config.RESULTS_DIR / f).exists() for f in
                                    [config.VALIDATION_JSON, config.BASELINE_RESULTS_JSON,
                                     config.FINAL_EVALUATION_JSON, config.RESULTS_JSON, config.AUDIT_JSON]}}))


@app.route("/api/dashboard-data", methods=["GET", "POST"])
def api_dashboard_data():
    try:
        return jsonify(clean({"status": "ok", **calculate_summary_stats()}))
    except Exception as exc:  # noqa: BLE001
        logger.exception("dashboard-data failed")
        return api_error(f"Could not build dashboard data: {getattr(exc, 'message', exc)}", 500, "SERVER_ERROR")


@app.route("/api/locations")
def api_locations():
    """Division -> district -> upazila hierarchy with the last data date of each place."""
    try:
        return jsonify(clean({"status": "ok", **get_engine().locations(), "horizons": get_settings().horizons}))
    except Exception as exc:  # noqa: BLE001
        if hasattr(exc, "code"):
            return dfs_error(exc)
        raise


@app.route("/api/units")
def api_units():
    level = request.args.get("level", "district")
    from src.geography import unit_table
    units = [u for u in unit_table(get_settings().geography) if u["level"] == level]
    if not units:
        return api_error("level must be national, division or district")
    return jsonify(clean({"status": "ok", "level": level, "units": units}))


# =============================================================================
# API - forecasts
# =============================================================================
def _horizon(body) -> Optional[int]:
    try:
        return int(body.get("horizon"))
    except (TypeError, ValueError):
        return None


@app.route("/api/forecast", methods=["POST"])
def api_forecast():
    body = request.get_json(silent=True) or {}
    unit = str(body.get("unit", "")).strip()
    h = _horizon(body)
    if not unit:
        return api_error("Choose a division, district or upazila.", code="MISSING_UNIT")
    if h is None:
        return api_error("Choose a forecast day (1-7).", code="MISSING_HORIZON")
    try:
        return jsonify(clean(get_engine().forecast(unit, h)))
    except Exception as exc:  # noqa: BLE001
        if hasattr(exc, "code") and hasattr(exc, "message"):
            return dfs_error(exc)
        raise


@app.route("/api/outlook", methods=["POST"])
def api_outlook():
    body = request.get_json(silent=True) or {}
    unit = str(body.get("unit", "")).strip()
    if not unit:
        return api_error("Choose a division, district or upazila.", code="MISSING_UNIT")
    try:
        return jsonify(clean(get_engine().outlook(unit)))
    except Exception as exc:  # noqa: BLE001
        if hasattr(exc, "code") and hasattr(exc, "message"):
            return dfs_error(exc)
        raise


@app.route("/api/forecast-all", methods=["POST"])
def api_forecast_all():
    body = request.get_json(silent=True) or {}
    level = str(body.get("level") or "district")
    h = _horizon(body)
    try:
        res = get_engine().forecast_all(level, [h] if h else None)
    except Exception as exc:  # noqa: BLE001
        if hasattr(exc, "code") and hasattr(exc, "message"):
            return dfs_error(exc)
        raise
    return jsonify(clean(res))


@app.route("/api/map", methods=["POST"])
def api_map():
    """District forecasts for one day + boundaries (choropleth on the forecast page)."""
    body = request.get_json(silent=True) or {}
    h = _horizon(body) or 1
    try:
        res = get_engine().forecast_all("district")          # 7-day results (cached), pick the day
    except Exception as exc:  # noqa: BLE001
        if hasattr(exc, "code") and hasattr(exc, "message"):
            return dfs_error(exc)
        raise
    geo_file = config.PROJECT_DIR / "data" / "reference" / "boundaries_district.geojson"
    geojson = json.loads(geo_file.read_text(encoding="utf-8"))
    vals = []
    for r in res["units"]:
        f = next((x for x in r["forecasts"] if x["horizon"] == h), None)
        if f:
            vals.append({"unit_code": r["unit_code"], "name": r["unit_name"], "predicted": f["predicted"],
                         "lower": f["lower_80"], "upper": f["upper_80"], "target_date": f["target_date"],
                         "method": r.get("method")})
    return jsonify(clean({"status": "ok", "horizon": h, "values": vals, "geojson": geojson}))


# =============================================================================
# API - model performance
# =============================================================================
@app.route("/api/model-metrics", methods=["POST"])
def api_model_metrics():
    body = request.get_json(silent=True) or {}
    level = str(body.get("level") or "district")
    unit = str(body.get("unit") or "").strip()
    h = _horizon(body) or 1
    fe = load_json_results(config.FINAL_EVALUATION_JSON)
    if not fe:
        return api_error("The final evaluation has not been run yet.", 503, "NOT_READY")
    um = load_csv(config.UNIT_METRICS_CSV)
    s = get_settings()
    by_h = []
    for hh in s.horizons:
        x = fe["levels"].get(level, {}).get("horizons", {}).get(f"h{hh}", {})
        row = {"horizon": hh, "all_MAE": x.get("test_MAE_deployed"), "all_RMSE": x.get("test_RMSE_deployed"),
               "all_Bias": x.get("test_Bias_deployed"), "all_R2": x.get("test_R2_deployed"),
               "baseline_MAE": x.get("test_MAE_best_baseline"), "baseline": x.get("best_baseline"),
               "model": x.get("deployed_model"), "coverage": x.get("interval_coverage_test"),
               "improvement": x.get("improvement_vs_baseline_pct")}
        if unit and um is not None:
            u = um[(um["level"] == level) & (um["unit_code"] == unit) & (um["horizon"] == hh)]
            if len(u):
                r = u.iloc[0]
                row.update({"unit_MAE": r["MAE"], "unit_RMSE": r["RMSE"], "unit_Bias": r["Bias"], "unit_R2": r["R2"],
                            "unit_baseline_MAE": r["baseline_MAE"], "unit_coverage": r.get("coverage"),
                            "unit_n": r["n"]})
        by_h.append(row)
    imp = load_csv(config.IMPORTANCE_CSV.format(level=level, h=h))
    importance = []
    if imp is not None:
        for r in imp.head(15).itertuples():
            importance.append({"feature": r.feature, "label": feature_label(r.feature),
                               "importance": r.importance, "std": r.std})
    residuals = []
    pred_file = config.PREDICTIONS_DIR / config.PREDICTIONS_FILE
    if pred_file.exists():
        p = pd.read_parquet(pred_file, columns=["level", "unit_code", "horizon", "y", "pred", "origin"])
        p = p[(p["level"] == level) & (p["horizon"] == h)]
        if unit:
            p = p[p["unit_code"] == unit]
        residuals = (p["pred"] - p["y"]).round(2).tolist()[:20000]
        series = (p.groupby("origin")[["y", "pred"]].sum().reset_index() if not unit else
                  p[["origin", "y", "pred"]].sort_values("origin"))
        series = [{"date": (d + pd.Timedelta(h, "D")).strftime("%Y-%m-%d"), "actual": a, "predicted": b}
                  for d, a, b in zip(series["origin"], series["y"], series["pred"])]
    else:
        series = []
    meta = json.loads((config.MODEL_METADATA_DIR / f"best_{level}_{h}d.json").read_text(encoding="utf-8")) \
        if (config.MODEL_METADATA_DIR / f"best_{level}_{h}d.json").exists() else {}
    topdown = []
    td = load_csv(config.TOPDOWN_CSV)
    if level == "district" and td is not None:
        t = td[(td["period"] == "test") & (td["horizon"] == h)]
        topdown = t[["staleness_days", "topdown_MAE", "direct_MAE", "rows"]].to_dict("records")
    return jsonify(clean({
        "status": "ok", "level": level, "unit": unit or None, "unit_name": unit_names().get(unit) if unit else None,
        "horizon": h, "by_horizon": by_h, "importance": importance, "residuals": residuals, "series": series,
        "topdown": topdown, "test_period": fe.get("test_period"),
        "model_info": {"deployed": meta.get("deployed_model"), "kind": meta.get("deployed_kind"),
                       "candidate": meta.get("candidate"), "best_baseline": meta.get("best_baseline"),
                       "trained_on": meta.get("trained_on"), "target_mode": meta.get("target_mode"),
                       "n_features": len(meta.get("features", [])), "intervals": meta.get("intervals")},
    }))


# =============================================================================
# API - uploads, data versions, pipeline runs
# =============================================================================
def _read_table(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""], encoding="utf-8-sig")
    df = pd.read_excel(path, dtype=object, engine="openpyxl")
    for c in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[c]) or df[c].map(lambda x: isinstance(x, datetime)).any():
            df[c] = pd.to_datetime(df[c], errors="coerce").dt.strftime("%Y-%m-%d")
    return df.astype("string")


def _saved_upload(name: str) -> Path:
    safe = secure_filename(name or "")
    path = (config.UPLOAD_FOLDER / safe).resolve()
    if not safe or config.UPLOAD_FOLDER.resolve() not in path.parents or not path.is_file():
        raise FileNotFoundError("That uploaded file is no longer available. Please upload it again.")
    return path


@app.route("/api/upload", methods=["POST"])
def api_upload():
    f = request.files.get("file")
    if f is None or not f.filename:
        return api_error("No file received (form field 'file').")
    ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
    if ext not in config.ALLOWED_EXTENSIONS:
        return api_error("Only DGHS .pdf reports, .csv and .xlsx files are accepted.", code="BAD_FILE_TYPE",
                         errors=[f"Unsupported file type '.{ext}'"])
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    saved = f"{stamp}_{secure_filename(f.filename) or 'upload.' + ext}"
    path = config.UPLOAD_FOLDER / saved
    f.save(path)
    try:
        if ext == "pdf":
            res = data_versions.preview_pdf(path, f.filename)
            if not res["is_valid"]:
                return jsonify(clean({"status": "error", "message": "This PDF could not be read as a DGHS daily "
                                      "dengue report.", **res}))
            return jsonify(clean({"status": "success", "saved_as": saved, "message": "Report read successfully"
                                  + (" (with warnings)" if res["warnings"] else ""), **res}))
        df = _read_table(path)
        v = data_versions.validate_table(df)
        if not v["is_valid"]:
            return jsonify(clean({"status": "error", "message": "Validation failed", "errors": v["errors"],
                                  "warnings": v["warnings"], "rows": v["rows"], "kind": "table"}))
        plan = data_versions.plan_table(v["clean"])
        names = unit_names()
        prev = v["clean"].head(config.PREVIEW_ROWS)
        return jsonify(clean({
            "status": "success", "kind": "table", "saved_as": saved, "rows": v["rows"], "warnings": v["warnings"],
            "errors": [], "message": "Data validated successfully" + (" (with warnings)" if v["warnings"] else ""),
            "merge": {k: val for k, val in plan.items() if not k.startswith("_")},
            "preview": [{"report_date": r.report_date.strftime("%Y-%m-%d"), "unit_code": r.unit_code,
                         "name": names.get(r.unit_code, r.unit_code), "admitted_24h": r.admitted_24h}
                        for r in prev.itertuples()]}))
    except Exception as exc:  # noqa: BLE001
        logger.exception("upload failed")
        return api_error("The file could not be read.", code="UNREADABLE_FILE",
                         errors=[f"{type(exc).__name__}: {getattr(exc, 'message', exc)}"])


@app.route("/api/apply-data", methods=["POST"])
def api_apply_data():
    body = request.get_json(silent=True) or {}
    mode = str(body.get("mode") or "data")
    if mode not in {m["key"] for m in mode_options()} or mode == "update":
        return api_error(f"Unknown run mode '{mode}'.", code="BAD_MODE")
    if runner.busy:
        return api_error("A pipeline run is already in progress.", code="RUN_IN_PROGRESS", status=409,
                         run=runner.state())
    try:
        path = _saved_upload(str(body.get("file") or ""))
    except FileNotFoundError as exc:
        return api_error(str(exc), code="UPLOAD_NOT_FOUND", status=404)
    try:
        if path.suffix.lower() == ".pdf":
            prev = data_versions.preview_pdf(path, path.name)
            if not prev["is_valid"]:
                return api_error("That PDF cannot be read, so it was not added.", code="VALIDATION_FAILED",
                                 errors=prev["errors"])
            entry = data_versions.apply_pdf(path, prev["report_date"])
            note = f"DGHS report for {prev['report_date']} ({path.name})"
        else:
            v = data_versions.validate_table(_read_table(path))
            if not v["is_valid"]:
                return api_error("That file does not pass validation, so it was not added.",
                                 code="VALIDATION_FAILED", errors=v["errors"])
            entry = data_versions.apply_table(v["clean"], path.name)
            note = f"{entry['rows_added']} rows from {path.name}"
    except ValueError as exc:
        return api_error(str(exc), code="NOTHING_NEW")
    except Exception as exc:  # noqa: BLE001
        logger.exception("apply-data failed")
        return api_error(f"The data could not be updated: {type(exc).__name__}: {exc}", 500, "WRITE_FAILED")
    _clear_caches()
    run = runner.start(mode, note=note, rollback_to=entry["restores_from"])
    return jsonify(clean({"status": "success", "version": entry, "run": run}))


@app.route("/api/data-status")
def api_data_status():
    try:
        summary = data_versions.summary()
    except Exception as exc:  # noqa: BLE001
        return api_error(f"The data status could not be read: {exc}", code="DATA_UNAVAILABLE", status=503)
    return jsonify(clean({"status": "success", "data": summary, "modes": mode_options(), "run": runner.state(),
                          "busy": runner.busy}))


@app.route("/api/pipeline-run")
def api_pipeline_run():
    return jsonify(clean({"status": "success", "run": runner.state(), "busy": runner.busy}))


@app.route("/api/pipeline-run/start", methods=["POST"])
def api_pipeline_start():
    body = request.get_json(silent=True) or {}
    mode = str(body.get("mode") or "update")
    if mode not in {m["key"] for m in mode_options()}:
        return api_error(f"Unknown run mode '{mode}'.", code="BAD_MODE")
    try:
        run = runner.start(mode, note="started from the web app")
    except RuntimeError as exc:
        return api_error(str(exc), code="RUN_IN_PROGRESS", status=409, run=runner.state())
    return jsonify(clean({"status": "success", "run": run}))


@app.route("/api/pipeline-run/cancel", methods=["POST"])
def api_pipeline_cancel():
    if not runner.cancel():
        return api_error("There is no run to cancel.", code="NO_RUN")
    return jsonify(clean({"status": "success", "message": "Stopping the run...", "run": runner.state()}))


@app.route("/api/data-versions/restore", methods=["POST"])
def api_restore_version():
    body = request.get_json(silent=True) or {}
    if runner.busy:
        return api_error("A pipeline run is in progress; wait for it to finish first.", code="RUN_IN_PROGRESS",
                         status=409)
    try:
        entry = data_versions.restore_version(str(body.get("id") or ""))
    except ValueError as exc:
        return api_error(str(exc), code="UNKNOWN_VERSION", status=404)
    run = runner.start("data", note=f"re-run after restoring {entry['id']}") if body.get("rerun", True) else None
    return jsonify(clean({"status": "success", "version": entry, "run": run,
                          "message": f"Data version {entry['id']} restored."}))


# =============================================================================
# API - files, figures, project log
# =============================================================================
@app.route("/api/downloads")
def api_downloads():
    files = []
    if config.RESULTS_DIR.exists():
        for p in sorted(config.RESULTS_DIR.iterdir()):
            if p.is_file() and p.suffix.lower() in config.DOWNLOAD_SUFFIXES:
                files.append({"name": p.name, "size_kb": round(p.stat().st_size / 1024, 1),
                              "modified": datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
                              "key": p.name in config.KEY_DOWNLOADS, "description": config.KEY_DOWNLOADS.get(p.name)})
    order = list(config.KEY_DOWNLOADS)
    files.sort(key=lambda f: (order.index(f["name"]) if f["key"] else len(order), f["name"]))
    return jsonify({"status": "ok", "files": files})


@app.route("/api/download/<path:filename>")
def api_download(filename: str):
    safe = secure_filename(filename)
    if not safe or safe != filename or Path(filename).suffix.lower() not in config.DOWNLOAD_SUFFIXES:
        return api_error("Invalid file name.", 400, "BAD_FILENAME")
    path = config.RESULTS_DIR / safe
    if not path.is_file() or path.resolve().parent != config.RESULTS_DIR.resolve():
        return api_error(f"File '{safe}' not found in results.", 404, "NOT_FOUND")
    return send_from_directory(config.RESULTS_DIR, safe, as_attachment=True)


@app.route("/api/figures")
def api_figures():
    figs = []
    if config.FIGURES_DIR.exists():
        order = list(config.FIGURE_TITLES)
        for p in sorted(config.FIGURES_DIR.glob("*.png"),
                        key=lambda p: (order.index(p.name) if p.name in order else len(order), p.name)):
            figs.append({"name": p.name, "title": config.FIGURE_TITLES.get(p.name) or p.stem.replace("_", " "),
                         "url": f"/figures/{p.name}"})
    return jsonify({"status": "ok", "figures": figs})


@app.route("/figures/<path:filename>")
def pipeline_figure(filename: str):
    safe = secure_filename(filename)
    if not safe or safe != filename or not safe.lower().endswith(".png"):
        return api_error("Invalid figure name.", 400, "BAD_FILENAME")
    return send_from_directory(config.FIGURES_DIR, safe)


@app.route("/api/project-log")
def api_project_log():
    """The continuation log (docs/PROGRESS_LOG.md), pipeline runs and web-app runs."""
    log_md = config.DOCS_DIR / "PROGRESS_LOG.md"
    text = log_md.read_text(encoding="utf-8") if log_md.exists() else "No progress log found."
    runs = []
    rdir = config.PROJECT_DIR / "logs" / "pipeline_runs"
    if rdir.exists():
        for f in sorted(rdir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:15]:
            try:
                r = json.loads(f.read_text(encoding="utf-8"))
                runs.append({"run_id": r.get("run_id"), "status": r.get("status"), "started": r.get("started_utc"),
                             "finished": r.get("finished_utc"),
                             "stages": [f"{x['stage']}:{x['status']}" for x in r.get("stages", [])]})
            except (OSError, ValueError):
                continue
    return jsonify(clean({"status": "ok", "markdown": text, "pipeline_runs": runs, "web_runs": runner.history(),
                          "audit": (load_json_results(config.AUDIT_JSON) or {}).get("pipeline_status")}))


# =============================================================================
# Errors
# =============================================================================
@app.errorhandler(413)
def too_large(_e):
    return api_error(f"File too large (max {config.MAX_FILE_SIZE // (1024 * 1024)} MB).", 413, "FILE_TOO_LARGE",
                     errors=["File too large"])


@app.errorhandler(HTTPException)
def http_error(e: HTTPException):
    if request.path.startswith("/api/"):
        return api_error(e.description or e.name, e.code or 500, e.name.upper().replace(" ", "_"))
    return render_template("error.html", code=e.code, title=e.name, message=e.description), e.code


@app.errorhandler(Exception)
def server_error(e: Exception):
    logger.exception("Unhandled error on %s", request.path)
    if request.path.startswith("/api/"):
        return api_error("Internal server error - see the server log.", 500, "SERVER_ERROR")
    return render_template("error.html", code=500, title="Server error",
                           message="Something went wrong. See the server log for details."), 500


@app.context_processor
def inject_globals():
    return {"project_dir": str(config.PROJECT_DIR), "year": datetime.now().year}


def port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1" if host == "0.0.0.0" else host, port)) == 0


if __name__ == "__main__":
    if not os.environ.get("WERKZEUG_RUN_MAIN") and port_in_use(config.HOST, config.PORT):
        logger.error("Port %d is already in use - the app is probably already running (open http://%s:%d). "
                     "Close that window first, or set DFS_PORT to another port.", config.PORT, config.HOST, config.PORT)
        sys.exit(1)
    logger.info("DFS web app - project: %s", config.PROJECT_DIR)
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG, threaded=True)
