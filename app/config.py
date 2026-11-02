"""Configuration for the DFS (Dengue Forecasting System) Flask web application.

The app reads the pipeline's outputs (JSON / CSV / parquet / .joblib) from the pipeline folder and reuses
the pipeline's own code (``src``) for forecasting, PDF parsing and validation, so the website computes
features exactly as training did (same design as the TFS weather app).

Override with environment variables (or a ``.env`` file next to this one):

    DFS_PROJECT_DIR   pipeline folder with results/, models/, data/, config/  (default: ../pipeline)
    DFS_CODE_DIR      folder with the pipeline package src/ and train_pipeline.py (default: ../pipeline)
    DFS_PORT / DFS_HOST   where the server listens (default 127.0.0.1:5001; TFS uses 5000)
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path

try:  # optional .env support
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:  # pragma: no cover
    pass

# ----------------------------------------------------------------------------- paths
BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = Path(os.environ.get("DFS_PROJECT_DIR", BASE_DIR.parent / "pipeline")).resolve()
CODE_DIR = Path(os.environ.get("DFS_CODE_DIR", BASE_DIR.parent / "pipeline")).resolve()   # folder with src/
DOCS_DIR = BASE_DIR.parent / "docs"
RESULTS_DIR = PROJECT_DIR / "results"
FIGURES_DIR = RESULTS_DIR / "figures"
MODELS_DIR = PROJECT_DIR / "models"
MODEL_METADATA_DIR = PROJECT_DIR / "model_metadata"
PREDICTIONS_DIR = PROJECT_DIR / "predictions"

# ----------------------------------------------------------------------------- uploads
UPLOAD_FOLDER = BASE_DIR / "static" / "uploads"
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
MAX_FILE_SIZE = int(os.environ.get("DFS_MAX_UPLOAD_MB", 25)) * 1024 * 1024
ALLOWED_EXTENSIONS = {"pdf", "csv", "xlsx"}
PREVIEW_ROWS = 10

# ----------------------------------------------------------------------------- flask
DEBUG = os.environ.get("DFS_DEBUG", "0") == "1"
TESTING = False
SECRET_KEY = os.environ.get("DFS_SECRET_KEY") or secrets.token_hex(16)
HOST = os.environ.get("DFS_HOST", "127.0.0.1")
PORT = int(os.environ.get("DFS_PORT", 5001))

# ----------------------------------------------------------------------------- pipeline files
RESULTS_JSON = "final_dengue_ml_results.json"
FINAL_EVALUATION_JSON = "09_final_evaluation.json"
UNIT_METRICS_CSV = "09_unit_metrics.csv"
TOPDOWN_CSV = "09_topdown_metrics.csv"
BASELINE_RESULTS_JSON = "06_baseline_results.json"
BASELINE_UNIT_CSV = "06_baseline_unit_metrics.csv"
ELIGIBILITY_CSV = "02_unit_eligibility.csv"
PREPARATION_JSON = "02_preparation_report.json"
VALIDATION_JSON = "01_validation_report.json"
AUDIT_JSON = "audit_report.json"
SCREENING_JSON = "07_screening_summary.json"
IMPORTANCE_CSV = "09_importance_{level}_h{h}.csv"
PREDICTIONS_FILE = "09_test_predictions.parquet"

DOWNLOAD_SUFFIXES = {".json", ".csv", ".md"}

KEY_DOWNLOADS = {
    "final_dengue_ml_results.json": "Master summary of the whole pipeline",
    "final_dengue_ml_results.md": "Readable results table (deployed model vs baseline per level and day)",
    "09_final_evaluation.json": "Final test-period evaluation and deployment decision per level and day",
    "09_unit_metrics.csv": "Test metrics of the deployed models per division/district and day",
    "09_topdown_metrics.csv": "Backtest of the top-down district method by data staleness",
    "audit_report.json": "Leakage and consistency audit (14 checks)",
    "08_tuning_summary.csv": "Hyperparameter tuning results per candidate",
    "07_screening_summary.json": "Model screening: top models per level and day",
    "06_baseline_results.json": "Baseline results on the CV folds",
    "02_unit_eligibility.csv": "Coverage and forecast eligibility of every division and district",
    "01_data_quality_summary.md": "Data quality summary of the DGHS reports",
    "00_parse_report.json": "PDF parsing summary (dates parsed, failures)",
}

FIGURE_TITLES = {
    "03_national_daily.png": "Bangladesh: daily dengue hospital admissions",
    "03_season_overlay.png": "Season comparison by year",
    "03_division_weekly.png": "Weekly admissions by division",
    "03_district_month_heatmap.png": "Mean daily admissions by month, 25 busiest districts",
    "03_weekday_effect.png": "Report-day effect",
    "03_autocorrelation.png": "Autocorrelation of admissions",
    "03_data_coverage.png": "Report coverage by month",
}

# Column names, horizons and thresholds come from the pipeline's config/config.json.
