"""Uploads and data versions for the DFS web app (adapted from the TFS ``data_versions``).

Two kinds of upload:
  * a DGHS Daily Dengue Press Release PDF -> parsed with the pipeline's own parser (preview), then copied
    into ``data/raw/pdfs/YYYY/YYYYMMDD_dengue_all.pdf`` and recorded in the PDF manifest (source = upload);
  * a CSV/XLSX table with columns ``report_date, unit_code`` (or ``district`` / ``division`` name) and
    ``admitted_24h`` -> district rows go to ``data/raw/manual_daily.csv``; division / national /
    Dhaka-metro rows go to ``data/raw/dashboard_daily.csv`` (source = manual_upload).
Existing PDF data is never overwritten by an upload.

Every apply first snapshots the editable files (manual_daily.csv, dashboard_daily.csv, the PDF manifest) to
``data/raw/versions/<id>/``; ``restore_version(id)`` puts them back and moves PDFs uploaded after that
version to ``data/raw/versions/removed_pdfs/`` (nothing is deleted).
"""
from __future__ import annotations

import csv
import json
import re
import shutil
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

import config

UNIT_ALIASES_EXTRA = {"dhaka metro": "DHAKA_METRO", "dhaka metropolitan": "DHAKA_METRO", "dncc+dscc": "DHAKA_METRO",
                      "bangladesh": "BD", "national": "BD", "total": "BD"}


def _settings():
    from src.config import load_settings
    from src.paths import ProjectPaths
    return load_settings(ProjectPaths(root=config.PROJECT_DIR))


def _raw() -> Path:
    return config.PROJECT_DIR / "data" / "raw"


def _versions_dir() -> Path:
    d = _raw() / "versions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _index() -> List[Dict[str, Any]]:
    f = _versions_dir() / "versions.json"
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []
    except ValueError:
        return []


def _save_index(items: List[Dict[str, Any]]) -> None:
    (_versions_dir() / "versions.json").write_text(json.dumps(items, indent=2), encoding="utf-8")


EDITABLE = ["manual_daily.csv", "dashboard_daily.csv", "pdfs/manifest.csv"]


def snapshot(note: str) -> Dict[str, Any]:
    items = _index()
    vid = f"v{len(items) + 1:04d}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    dest = _versions_dir() / vid
    dest.mkdir(parents=True, exist_ok=True)
    for name in EDITABLE:
        src = _raw() / name
        if src.exists():
            target = dest / name.replace("/", "__")
            shutil.copy2(src, target)
    entry = {"id": vid, "created": datetime.now().isoformat(timespec="seconds"), "note": note,
             "pdfs_on_disk": sorted(p.relative_to(_raw()).as_posix() for p in (_raw() / "pdfs").rglob("*.pdf"))}
    items.append(entry)
    _save_index(items)
    return entry


def restore_version(version_id: str) -> Dict[str, Any]:
    items = _index()
    entry = next((e for e in items if e["id"] == version_id), None)
    if entry is None:
        raise ValueError(f"Unknown data version '{version_id}'.")
    src_dir = _versions_dir() / version_id
    for name in EDITABLE:
        snap = src_dir / name.replace("/", "__")
        target = _raw() / name
        if snap.exists():
            shutil.copy2(snap, target)
        elif target.exists() and name == "manual_daily.csv":
            target.unlink()
    keep = set(entry.get("pdfs_on_disk", []))
    removed = []
    for p in (_raw() / "pdfs").rglob("*.pdf"):
        rel = p.relative_to(_raw()).as_posix()
        if rel not in keep:
            dest = _versions_dir() / "removed_pdfs" / p.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(p), str(dest))
            removed.append(rel)
    return {**entry, "removed_pdfs": removed, "restored": datetime.now().isoformat(timespec="seconds")}


# ------------------------------------------------------------------------------------------------
# PDF uploads
# ------------------------------------------------------------------------------------------------
def _date_from_name(name: str) -> Optional[date]:
    m = re.search(r"(20\d{2})(\d{2})(\d{2})", name)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None


def preview_pdf(path: Path, original_name: str) -> Dict[str, Any]:
    from src.acquire import read_manifest
    from src.ingest import parse_one
    from src.pdf_parser import parse_pdf

    s = _settings()
    geo = s.geography
    rep = parse_pdf(path, None, geo)
    d = rep.printed_date or _date_from_name(original_name)
    if d is None:
        return {"is_valid": False, "errors": ["The report date could not be read from the PDF or the file name "
                                               "(expected e.g. 20261012_dengue_all.pdf)."], "warnings": []}
    parsed = parse_one(path, d, geo)
    errors = [i for i in parsed["issues"] if "unmapped" in i or "not found" in i or "blocks" in i]
    warnings = [i for i in parsed["issues"] if i not in errors]
    if parsed["status"] == "failed" and not errors:
        errors = parsed["issues"][:5] or ["The district table could not be read."]
    man = read_manifest(s.paths.pdf_manifest)
    exists = man.get(d.isoformat(), {}).get("status") == "ok"
    recs = sorted(parsed["records"], key=lambda r: -(r["admitted_24h"] or 0))
    names = {x["code"]: x["name"] for dv in geo["divisions"] for x in dv["districts"]}
    names[geo["metro"]["code"]] = geo["metro"]["name"]
    return {"kind": "pdf", "is_valid": parsed["status"] != "failed", "report_date": d.isoformat(),
            "printed_date": parsed.get("printed_date"), "errors": errors, "warnings": warnings,
            "units": len(recs), "national_24h": (parsed.get("checks") or {}).get("table_national_24h"),
            "national_matches": (parsed.get("checks") or {}).get("national_matches"),
            "already_present": exists,
            "preview": [{"unit_code": r["unit_code"], "name": names.get(r["unit_code"], r["unit_code"]),
                         "admitted_24h": r["admitted_24h"], "cum_admitted": r["cum_admitted"]}
                        for r in recs[: config.PREVIEW_ROWS]]}


def apply_pdf(path: Path, report_date: str) -> Dict[str, Any]:
    from src.acquire import read_manifest, write_manifest
    from src.utils import sha256_file, utc_now_iso

    s = _settings()
    d = date.fromisoformat(report_date)
    man = read_manifest(s.paths.pdf_manifest)
    if man.get(report_date, {}).get("status") == "ok":
        raise ValueError(f"A DGHS PDF for {report_date} is already in the data; nothing was added.")
    entry = snapshot(f"before adding uploaded PDF for {report_date}")
    target = s.paths.pdfs / f"{d:%Y}" / f"{d:%Y%m%d}_dengue_all.pdf"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)
    man[report_date] = {"report_date": report_date, "url": f"upload:{path.name}", "status": "ok", "http_status": "",
                        "bytes": str(target.stat().st_size), "sha256": sha256_file(target),
                        "file": s.paths.relative(target), "checked_utc": utc_now_iso()}
    write_manifest(s.paths.pdf_manifest, man)
    return {"restores_from": entry["id"], "rows_added": 65, "report_date": report_date}


# ------------------------------------------------------------------------------------------------
# table uploads
# ------------------------------------------------------------------------------------------------
def _unit_lookup(geo: Dict) -> Dict[str, str]:
    look = dict(UNIT_ALIASES_EXTRA)
    for dv in geo["divisions"]:
        look[dv["code"].lower()] = dv["code"]
        look[dv["name"].lower()] = dv["code"]
        look[dv["name_bn"]] = dv["code"]
        look[(dv["name"] + " division").lower()] = dv["code"]
        for x in dv["districts"]:
            look[x["code"].lower()] = x["code"]
            look[x["name"].lower()] = x["code"]
            look[x["name_bn"]] = x["code"]
    look[geo["metro"]["code"].lower()] = geo["metro"]["code"]
    look["bd"] = "BD"
    return look


def validate_table(df: pd.DataFrame) -> Dict[str, Any]:
    s = _settings()
    geo = s.geography
    cols = {c.strip().lower(): c for c in df.columns}
    errors, warnings = [], []
    dcol = next((cols[c] for c in ["report_date", "date"] if c in cols), None)
    ucol = next((cols[c] for c in ["unit_code", "district", "division", "unit", "place"] if c in cols), None)
    vcol = next((cols[c] for c in ["admitted_24h", "admissions", "new_cases", "cases"] if c in cols), None)
    for need, col in (("report_date", dcol), ("unit_code / district", ucol), ("admitted_24h", vcol)):
        if col is None:
            errors.append(f"Missing column '{need}'.")
    if errors:
        return {"is_valid": False, "errors": errors, "warnings": [], "rows": len(df)}
    look = _unit_lookup(geo)
    out = pd.DataFrame({"raw_date": df[dcol].astype(str).str.strip(), "raw_unit": df[ucol].astype(str).str.strip(),
                        "raw_value": df[vcol]})
    out["report_date"] = pd.to_datetime(out["raw_date"], errors="coerce", format="mixed", dayfirst=True)
    out["unit_code"] = out["raw_unit"].map(lambda u: look.get(u.lower(), look.get(u)))
    out["admitted_24h"] = pd.to_numeric(out["raw_value"], errors="coerce")
    bad_d = out["report_date"].isna()
    bad_u = out["unit_code"].isna()
    bad_v = out["admitted_24h"].isna() | (out["admitted_24h"] < 0) | (out["admitted_24h"] % 1 != 0)
    if bad_d.any():
        errors.append(f"{int(bad_d.sum())} rows with an unreadable date (use YYYY-MM-DD), e.g. "
                      f"'{out.loc[bad_d, 'raw_date'].iloc[0]}'.")
    if bad_u.any():
        errors.append(f"{int(bad_u.sum())} rows with an unknown place, e.g. '{out.loc[bad_u, 'raw_unit'].iloc[0]}' "
                      "(use the district/division English name or code, e.g. BD3029 or Faridpur).")
    if bad_v.any():
        errors.append(f"{int(bad_v.sum())} rows where admitted_24h is not a whole number >= 0.")
    future = out["report_date"] > pd.Timestamp(date.today())
    if future.any():
        errors.append(f"{int(future.sum())} rows are dated in the future.")
    dup = out.duplicated(["report_date", "unit_code"])
    if dup.any():
        errors.append(f"{int(dup.sum())} duplicate (date, place) rows.")
    big = out["admitted_24h"] > s.config["data"]["max_plausible_unit_admissions"]
    if big.any():
        warnings.append(f"{int(big.sum())} rows above {s.config['data']['max_plausible_unit_admissions']} admissions "
                        "in a day - check them.")
    ok = out[~(bad_d | bad_u | bad_v)].copy()
    return {"is_valid": not errors, "errors": errors, "warnings": warnings, "rows": len(df), "clean": ok}


def plan_table(clean: pd.DataFrame) -> Dict[str, Any]:
    from src.geography import district_codes

    s = _settings()
    dist = set(district_codes(s.geography)) - {s.geography["metro"]["code"]}
    daily = pd.read_csv(s.paths.raw_daily, parse_dates=["report_date"]) if s.paths.raw_daily.exists() else pd.DataFrame(
        columns=["report_date", "unit_code"])
    have_pdf = set(zip(daily["report_date"], daily["unit_code"]))
    is_dist = clean["unit_code"].isin(dist)
    in_pdf = [(d, u) in have_pdf for d, u in zip(clean["report_date"], clean["unit_code"])]
    clean = clean.assign(in_pdf=in_pdf)
    new = clean[~clean["in_pdf"]]
    return {"rows": int(len(clean)), "district_rows": int(is_dist.sum()), "other_rows": int((~is_dist).sum()),
            "already_in_pdf_data": int(clean["in_pdf"].sum()), "new_rows": int(len(new)),
            "first_date": str(clean["report_date"].min().date()) if len(clean) else None,
            "last_date": str(clean["report_date"].max().date()) if len(clean) else None, "_new": new, "_dist": dist}


def apply_table(clean: pd.DataFrame, source_name: str) -> Dict[str, Any]:
    p = plan_table(clean)
    new = p["_new"]
    if new.empty:
        raise ValueError("Every row in that file is already in the data, so there is nothing to add.")
    entry = snapshot(f"before adding {len(new)} rows from {source_name}")
    dist_rows = new[new["unit_code"].isin(p["_dist"])]
    other = new[~new["unit_code"].isin(p["_dist"])]
    if len(dist_rows):
        f = _raw() / "manual_daily.csv"
        old = pd.read_csv(f) if f.exists() else pd.DataFrame(columns=["report_date", "unit_code", "admitted_24h", "source"])
        add = pd.DataFrame({"report_date": dist_rows["report_date"].dt.strftime("%Y-%m-%d"),
                            "unit_code": dist_rows["unit_code"], "admitted_24h": dist_rows["admitted_24h"].astype(int),
                            "source": f"upload:{source_name}"})
        merged = pd.concat([old, add], ignore_index=True).drop_duplicates(["report_date", "unit_code"], keep="last")
        merged.sort_values(["report_date", "unit_code"]).to_csv(f, index=False)
    if len(other):
        f = _raw() / "dashboard_daily.csv"
        old = pd.read_csv(f) if f.exists() else pd.DataFrame(
            columns=["report_date", "unit_code", "admitted_24h", "deaths_24h", "source", "retrieved_utc"])
        add = pd.DataFrame({"report_date": other["report_date"].dt.strftime("%Y-%m-%d"), "unit_code": other["unit_code"],
                            "admitted_24h": other["admitted_24h"].astype(int), "deaths_24h": 0,
                            "source": "manual_upload", "retrieved_utc": datetime.now().isoformat(timespec="seconds")})
        merged = pd.concat([old, add], ignore_index=True).drop_duplicates(["report_date", "unit_code"], keep="last")
        merged.sort_values(["report_date", "unit_code"]).to_csv(f, index=False)
    return {"restores_from": entry["id"], "rows_added": int(len(new)), "district_rows": int(len(dist_rows)),
            "other_rows": int(len(other))}


# ------------------------------------------------------------------------------------------------
# status
# ------------------------------------------------------------------------------------------------
def summary() -> Dict[str, Any]:
    from src.acquire import manifest_summary

    s = _settings()
    ms = manifest_summary(s.paths)
    dash = _raw() / "dashboard_daily.csv"
    dash_dates = []
    if dash.exists():
        with dash.open(encoding="utf-8") as f:
            dash_dates = sorted({r["report_date"] for r in csv.DictReader(f)})
    manual = _raw() / "manual_daily.csv"
    n_manual = sum(1 for _ in manual.open(encoding="utf-8")) - 1 if manual.exists() else 0
    uploads = sum(1 for r in csv.DictReader(s.paths.pdf_manifest.open(encoding="utf-8"))
                  if str(r.get("url", "")).startswith("upload:")) if s.paths.pdf_manifest.exists() else 0
    return {"pdfs": ms, "uploaded_pdfs": uploads,
            "dashboard": {"dates": len(dash_dates), "first": dash_dates[0] if dash_dates else None,
                          "last": dash_dates[-1] if dash_dates else None},
            "manual_rows": max(n_manual, 0),
            "versions": list(reversed([{k: v for k, v in e.items() if k != "pdfs_on_disk"} for e in _index()]))[:20]}
