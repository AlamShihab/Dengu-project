"""DFS web app tests (Flask test client, real pipeline folder). Nothing here changes the pipeline's data:
uploads go to a temporary folder and are only checked, never applied."""
import io
import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))

import app as webapp  # noqa: E402
import config  # noqa: E402

FIX = APP_DIR.parent / "pipeline" / "tests" / "fixtures"
READY = (config.RESULTS_DIR / config.FINAL_EVALUATION_JSON).exists()
needs_models = pytest.mark.skipif(not READY, reason="models not trained yet")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "UPLOAD_FOLDER", tmp_path)
    webapp.app.config["TESTING"] = True
    return webapp.app.test_client()


@pytest.mark.parametrize("page", ["/", "/forecast", "/model-performance", "/data-upload", "/project-log"])
def test_pages(client, page):
    r = client.get(page)
    assert r.status_code == 200
    assert b"DFS Dashboard" in r.data


def test_unknown_page_is_404(client):
    assert client.get("/no-such-page").status_code == 404


def test_status_and_dashboard(client):
    s = client.get("/api/status").get_json()
    assert s["config_ok"] and s["horizons"] == [1, 2, 3, 4, 5, 6, 7]
    d = client.get("/api/dashboard-data").get_json()
    assert d["status"] == "ok"
    assert d["units"]["districts"] == 65 and d["units"]["divisions"] == 8


def test_units(client):
    d = client.get("/api/units?level=division").get_json()
    assert len(d["units"]) == 8
    assert client.get("/api/units?level=planet").status_code == 400


@needs_models
def test_locations_hierarchy(client):
    d = client.get("/api/locations").get_json()
    assert len(d["divisions"]) == 8
    dhaka = next(x for x in d["divisions"] if x["code"] == "BD30")
    assert any(x["code"] == "DHAKA_METRO" for x in dhaka["districts"])
    assert sum(len(x["districts"]) for x in d["divisions"]) == 65


@needs_models
def test_outlook_seven_days(client):
    d = client.post("/api/outlook", json={"unit": "BD3029"}).get_json()
    assert d["status"] == "success"
    assert [f["horizon"] for f in d["forecasts"]] == [1, 2, 3, 4, 5, 6, 7]
    assert len(d["history"]) > 0


@needs_models
def test_single_day_and_errors(client):
    d = client.post("/api/forecast", json={"unit": "BD30", "horizon": 4}).get_json()
    assert d["status"] == "success" and d["forecast"]["horizon"] == 4
    assert client.post("/api/forecast", json={"unit": "XX", "horizon": 1}).status_code == 404
    assert client.post("/api/forecast", json={"unit": "BD30", "horizon": 9}).status_code == 400
    assert client.post("/api/forecast", json={"horizon": 1}).status_code == 400


@needs_models
def test_upazila_and_all(client):
    d = client.post("/api/outlook", json={"unit": "BD100409"}).get_json()
    assert d["unit_code"] == "BD1004" and d["requested_name"] == "Amtali"
    a = client.post("/api/forecast-all", json={"level": "division"}).get_json()
    assert len(a["units"]) == 8
    m = client.post("/api/map", json={"horizon": 2}).get_json()
    assert m["status"] == "ok" and len(m["geojson"]["features"]) == 64


@needs_models
def test_model_metrics(client):
    d = client.post("/api/model-metrics", json={"level": "district", "unit": "BD3029", "horizon": 1}).get_json()
    assert d["status"] == "ok" and len(d["by_horizon"]) == 7


def test_upload_csv_ok(client):
    csv = "report_date,district,admitted_24h\n2026-10-01,Faridpur,12\n2026-10-01,Dhaka Metro,300\n"
    r = client.post("/api/upload", data={"file": (io.BytesIO(csv.encode()), "extra.csv")},
                    content_type="multipart/form-data").get_json()
    assert r["status"] == "success", r
    assert r["merge"]["rows"] == 2 and r["merge"]["district_rows"] == 1


def test_upload_csv_errors(client):
    csv = "report_date,district,admitted_24h\n2026-10-01,Atlantis,12\nnot-a-date,Faridpur,-3\n"
    r = client.post("/api/upload", data={"file": (io.BytesIO(csv.encode()), "bad.csv")},
                    content_type="multipart/form-data").get_json()
    assert r["status"] == "error" and len(r["errors"]) >= 2


def test_upload_pdf_preview(client):
    data = (FIX / "20260903_dengue_all.pdf").read_bytes()
    r = client.post("/api/upload", data={"file": (io.BytesIO(data), "20260903_dengue_all.pdf")},
                    content_type="multipart/form-data").get_json()
    assert r["status"] == "success", r
    assert r["report_date"] == "2026-09-03" and r["units"] == 65 and r["national_24h"] == 1252


def test_upload_wrong_type(client):
    r = client.post("/api/upload", data={"file": (io.BytesIO(b"x"), "a.exe")}, content_type="multipart/form-data")
    assert r.status_code == 400


def test_download_rejects_path_traversal(client):
    assert client.get("/api/download/..%2Fconfig%2Fconfig.json").status_code in (400, 404)
    assert client.get("/api/download/evil.exe").status_code == 400


def test_project_log(client):
    d = client.get("/api/project-log").get_json()
    assert d["status"] == "ok" and "Progress log" in d["markdown"]
