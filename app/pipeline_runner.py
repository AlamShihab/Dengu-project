"""Runs the DFS pipeline in the background for the web app (adapted from the TFS runner).

One run at a time. Each stage is a separate process (``python train_pipeline.py --only <stage>`` or a
download script), so a crashing stage cannot take the web server down and the app always knows which
stage is active. Progress is kept in memory and mirrored to ``logs/webapp_runs/<run_id>.json``.

Modes
``update``   download new DGHS PDFs and dashboard days, then rebuild the daily data. The deployed models
             forecast from the new last day at once. Needs the internet. Minutes.
``data``     rebuild the daily data from what is on disk (after an upload). Seconds.
``refresh``  the data stages, features, baselines, then refit and re-evaluate the deployed model
             families (no new screening/tuning). Minutes.
``full``     everything including screening and tuning (saved results are archived first, never
             deleted). Hours.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import config

DATA_STAGES = ["ingest", "setup", "validate", "prepare"]
MODEL_PREP = ["split", "features", "baselines"]
HEAVY_STAGES = ["screening", "tuning"]
FINAL_STAGES = ["evaluate", "audit"]

MODES: Dict[str, Dict[str, Any]] = {
    "update": {
        "label": "Get the latest DGHS data",
        "stages": ["download", "dashboard"] + DATA_STAGES,
        "description": ("Downloads any new DGHS daily press-release PDFs (district data) and the dashboard's "
                        "division / national figures up to today, then rebuilds the daily data. The deployed "
                        "models forecast from the new last day immediately. Needs the internet; a few minutes."),
    },
    "data": {
        "label": "Update the data only",
        "stages": DATA_STAGES,
        "description": ("Rebuilds the daily data from the files on disk (for example after uploading DGHS "
                        "PDFs). The existing models forecast from the new last day; accuracy figures keep "
                        "coming from the last full evaluation. Seconds."),
    },
    "refresh": {
        "label": "Rebuild and refit",
        "stages": DATA_STAGES + MODEL_PREP + FINAL_STAGES,
        "description": ("Also rebuilds the features and baselines and refits / re-evaluates the deployed model "
                        "families with their tuned settings. Several minutes."),
    },
    "full": {
        "label": "Full re-analysis",
        "stages": DATA_STAGES + MODEL_PREP + HEAVY_STAGES + FINAL_STAGES,
        "description": ("Everything, including model screening (17 models) and hyperparameter tuning from "
                        "scratch. The most faithful option and by far the slowest (hours)."),
    },
}

STAGE_TITLES = {
    "download": "Download new DGHS PDFs",
    "dashboard": "Fetch DGHS dashboard (divisions / national)",
    "ingest": "Parse PDFs into the raw dataset",
    "setup": "Project setup & configuration",
    "validate": "Data validation & QC",
    "prepare": "Preparation & EDA",
    "split": "Temporal split & leakage control",
    "features": "Feature engineering",
    "baselines": "Baselines",
    "screening": "Model screening",
    "tuning": "Hyperparameter tuning",
    "evaluate": "Final evaluation & model selection",
    "audit": "Reporting & audit",
}
LOG_TAIL_LINES = 40


def mode_options() -> List[Dict[str, Any]]:
    return [{"key": k, "label": v["label"], "description": v["description"],
             "stages": [STAGE_TITLES[s] for s in v["stages"]]} for k, v in MODES.items()]


class PipelineRunner:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state: Optional[Dict[str, Any]] = None
        self._process: Optional[subprocess.Popen] = None
        self._cancel = threading.Event()
        self.on_finish = None          # callback(state) - the app clears its caches

    # ------------------------------------------------------------------ state
    @property
    def busy(self) -> bool:
        with self._lock:
            return bool(self._state and self._state["status"] == "running")

    def state(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            if self._state is not None:
                return json.loads(json.dumps(self._state))
        return self._last_persisted()

    def _runs_dir(self) -> Path:
        d = config.PROJECT_DIR / "logs" / "webapp_runs"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _last_persisted(self) -> Optional[Dict[str, Any]]:
        try:
            files = sorted(self._runs_dir().glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            return json.loads(files[0].read_text(encoding="utf-8")) if files else None
        except (OSError, ValueError, IndexError):
            return None

    def history(self, n: int = 10) -> List[Dict[str, Any]]:
        out = []
        for f in sorted(self._runs_dir().glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:n]:
            try:
                s = json.loads(f.read_text(encoding="utf-8"))
                out.append({k: s.get(k) for k in ["run_id", "mode_label", "status", "started", "finished", "message", "note"]})
            except (OSError, ValueError):
                continue
        return out

    def _persist(self) -> None:
        if not self._state:
            return
        try:
            (self._runs_dir() / f"{self._state['run_id']}.json").write_text(json.dumps(self._state, indent=2),
                                                                            encoding="utf-8")
        except OSError:
            pass

    def _set(self, **fields: Any) -> None:
        with self._lock:
            if self._state is not None:
                self._state.update(fields)
        self._persist()

    def _update_stage(self, key: str, **fields: Any) -> None:
        with self._lock:
            if self._state is None:
                return
            for st in self._state["stages"]:
                if st["key"] == key:
                    st.update(fields)
        self._persist()

    # ------------------------------------------------------------------ control
    def start(self, mode: str, *, note: str = "", rollback_to: Optional[str] = None) -> Dict[str, Any]:
        if mode not in MODES:
            raise ValueError(f"Unknown run mode '{mode}'. Use one of: {', '.join(MODES)}")
        with self._lock:
            if self._state and self._state["status"] == "running":
                raise RuntimeError("A pipeline run is already in progress.")
            run_id = f"WEB_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            self._state = {"run_id": run_id, "mode": mode, "mode_label": MODES[mode]["label"], "status": "running",
                           "started": datetime.now().isoformat(timespec="seconds"), "finished": None, "note": note,
                           "rollback_to": rollback_to, "rolled_back": None, "current_stage": None,
                           "stages": [{"key": k, "title": STAGE_TITLES[k], "status": "pending", "seconds": None,
                                       "log": []} for k in MODES[mode]["stages"]],
                           "message": "Starting..."}
            self._cancel.clear()
        self._persist()
        threading.Thread(target=self._run, name=f"dfs-{run_id}", daemon=True).start()
        return self.state()

    def cancel(self) -> bool:
        with self._lock:
            if not (self._state and self._state["status"] == "running"):
                return False
            self._cancel.set()
            proc = self._process
        if proc and proc.poll() is None:
            try:
                proc.terminate()
            except OSError:
                pass
        return True

    # ------------------------------------------------------------------ running
    def _command(self, key: str) -> List[str]:
        py = sys.executable
        if key == "download":
            return [py, str(config.CODE_DIR / "scripts" / "00_download_pdfs.py"), "--update"]
        if key == "dashboard":
            return [py, str(config.CODE_DIR / "scripts" / "00_fetch_dashboard.py")]
        return [py, str(config.CODE_DIR / "train_pipeline.py"), "--only", key]

    def _archive_heavy(self) -> Optional[str]:
        exp = config.PROJECT_DIR / "experiments"
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = exp / f"archive_{stamp}"
        moved = 0
        for name in ("screening", "tuning"):
            src = exp / name
            if src.is_dir() and any(src.iterdir()):
                (dest / name).mkdir(parents=True, exist_ok=True)
                for item in list(src.iterdir()):
                    try:
                        shutil.move(str(item), str(dest / name / item.name))
                        moved += 1
                    except (OSError, shutil.Error):
                        pass
        return dest.name if moved else None

    def _run(self) -> None:
        mode = self._state["mode"]
        try:
            for st in list(self._state["stages"]):
                key = st["key"]
                if self._cancel.is_set():
                    self._update_stage(key, status="skipped")
                    continue
                if mode == "full" and key == "screening":
                    self._set(archived_to=self._archive_heavy())
                self._set(current_stage=key, message=f"{STAGE_TITLES[key]}...")
                self._update_stage(key, status="running")
                began = datetime.now()
                code, tail = self._run_stage(key)
                secs = round((datetime.now() - began).total_seconds(), 1)
                if self._cancel.is_set():
                    self._update_stage(key, status="cancelled", seconds=secs, log=tail)
                    return self._finish("cancelled", "The run was cancelled.")
                ok = code == 0 or (key in ("download", "dashboard") and code == 2)   # 2 = some dates unavailable
                if not ok:
                    self._update_stage(key, status="failed", seconds=secs, log=tail)
                    return self._fail(f"Stage '{STAGE_TITLES[key]}' failed. "
                                      + (tail[-1] if tail else "See the log below."))
                self._update_stage(key, status="completed", seconds=secs, log=tail)
            self._finish("completed", "The pipeline finished. The website now shows the new results.")
        except Exception as exc:  # noqa: BLE001
            self._fail(f"The run stopped unexpectedly: {type(exc).__name__}: {exc}")

    def _run_stage(self, key: str) -> tuple:
        env = {**os.environ, "DFS_ROOT": str(config.PROJECT_DIR), "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
        tail: List[str] = []
        try:
            proc = subprocess.Popen(self._command(key), cwd=str(config.CODE_DIR), env=env, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except OSError as exc:
            return 1, [f"Could not start the stage: {exc}"]
        with self._lock:
            self._process = proc
        for line in proc.stdout:
            line = line.rstrip()
            if not line:
                continue
            tail.append(line[-300:])
            tail = tail[-LOG_TAIL_LINES:]
            self._update_stage(key, log=tail)
        code = proc.wait()
        with self._lock:
            self._process = None
        return code, tail

    def _fail(self, message: str) -> None:
        rb = self._state.get("rollback_to")
        if rb:
            try:
                import data_versions
                data_versions.restore_version(rb)
                self._set(rolled_back=rb)
                message += f" The data was restored to version {rb}."
            except Exception as exc:  # noqa: BLE001
                message += f" Restoring the previous data failed: {exc}"
        self._finish("failed", message)

    def _finish(self, status: str, message: str) -> None:
        self._set(status=status, message=message, finished=datetime.now().isoformat(timespec="seconds"),
                  current_stage=None)
        if self.on_finish:
            try:
                self.on_finish(self.state())
            except Exception:  # noqa: BLE001
                pass


runner = PipelineRunner()
