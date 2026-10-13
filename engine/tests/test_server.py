import base64
import io

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from plush.server import app_from_env, create_app

from kits import bear, part


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    return TestClient(create_app(tmp_path_factory.mktemp("projects")))


def new_project(client, name="bear"):
    body = {"name": name, "picture_base64": base64.b64encode(b"\x89PNG test picture").decode(), "media_type": "image/png"}
    return client.post("/api/projects", json=body).json()["slug"]


def test_service_will_not_start_without_picture_reading_settings(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("PLUSH_VISION_MODEL", raising=False)
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY and PLUSH_VISION_MODEL"):
        app_from_env()


def test_picture_reading_says_when_it_is_not_set_up(client):
    slug = new_project(client)
    response = client.post(f"/api/projects/{slug}/read")
    assert response.status_code == 503 and "PLUSH_VISION_MODEL" in response.json()["detail"]


def test_an_invalid_kit_is_rejected_with_the_reason(client):
    slug = new_project(client)
    kit = bear()
    part(kit, "arm")["end_shape"] = "claw"
    response = client.put(f"/api/projects/{slug}/kit", json=kit)
    assert response.status_code == 422
    assert any("end_shape" in str(e["loc"]) for e in response.json()["detail"])


def test_mesh_returns_every_placed_part(client):
    slug = new_project(client)
    assert client.put(f"/api/projects/{slug}/kit", json=bear()).status_code == 200
    parts = client.post(f"/api/projects/{slug}/mesh", json={"finished_height_in": 12}).json()["parts"]
    assert set(parts) == {"body", "head", "ear_left", "ear_right", "arm_left", "arm_right", "eye_left", "eye_right"}
    assert all(len(p["vertices"]) > 0 and len(p["faces"]) > 0 for p in parts.values())


def test_no_pattern_without_approval(client):
    slug = new_project(client)
    client.put(f"/api/projects/{slug}/kit", json=bear())
    assert client.post(f"/api/projects/{slug}/pattern").status_code == 409
    assert client.get(f"/api/projects/{slug}/pattern.pdf").status_code == 404


def test_approved_bear_builds_a_pattern_that_passes_all_seven_checks(client):
    slug = new_project(client)
    client.put(f"/api/projects/{slug}/kit", json=bear())
    vid = client.post(f"/api/projects/{slug}/approve", json={"finished_height_in": 12}).json()["version_id"]
    response = client.post(f"/api/projects/{slug}/pattern")
    report = response.json()
    assert response.status_code == 200, [c for c in report["checks"] if not c["passed"]]
    assert [c["number"] for c in report["checks"]] == [1, 2, 3, 4, 5, 6, 7]
    assert report["version_id"] == vid
    pdf = client.get(f"/api/projects/{slug}/pattern.pdf")
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
    cover = PdfReader(io.BytesIO(pdf.content)).pages[0].extract_text()
    assert f"version {vid[:12]}" in cover  # the printed pattern carries its approved version
