"""Тесты HTTP-слоя: контракт ответа, ошибки, CORS и то, что файл не пишется на диск."""

import io
import tempfile
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main

DEMO = (Path(__file__).resolve().parents[2] / "examples" / "demo_chat.txt").read_bytes()
REPORT_KEYS = {
    "meta", "summary", "participants", "response_times", "calls",
    "activity", "timeline", "top_words", "top_emoji", "warnings",
}

client = TestClient(main.app)


def upload(data: bytes, filename: str = "chat.txt", **params):
    return client.post("/api/analyze", files={"file": (filename, data)}, params=params)


def test_health():
    assert client.get("/api/health").json() == {"status": "ok", "max_upload_mb": main.MAX_UPLOAD_MB}


def test_analyze_txt():
    response = upload(DEMO)
    assert response.status_code == 200
    report = response.json()
    assert set(report) == REPORT_KEYS
    assert report["summary"]["messages"] > 0


def test_analyze_zip():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("_chat.txt", DEMO)
        zf.writestr("00000001-PHOTO.jpg", b"\xff\xd8 not really a photo")
    response = upload(buf.getvalue(), "WhatsApp Chat.zip")
    assert response.status_code == 200
    assert response.json()["summary"] == upload(DEMO).json()["summary"]


def test_gap_hours_param():
    def starts(gap):
        return sum(p["initiations"] for p in upload(DEMO, gap_hours=gap).json()["participants"])

    assert starts(1) > starts(6) > starts(24)
    assert upload(DEMO, gap_hours=0).status_code == 422  # gt=0


@pytest.mark.parametrize(
    ("data", "detail"),
    [(b"", "пустой"), (b"just some notes\nnot a chat", "формат")],
)
def test_unparseable_file(data, detail):
    response = upload(data)
    assert response.status_code == 422
    assert detail in response.json()["detail"]


def test_request_errors():
    assert client.post("/api/analyze", json={"file": "x"}).status_code == 415
    no_file = client.post("/api/analyze", data={"note": "без файла"}, files={"other": ("a.txt", b"")})
    assert no_file.status_code == 400
    assert "file" in no_file.json()["detail"]


def test_too_large(monkeypatch):
    monkeypatch.setattr(main, "MAX_UPLOAD_BYTES", 1000)
    response = upload(b"x" * 2000)
    assert response.status_code == 413


def test_upload_never_touches_disk(monkeypatch):
    """SpooledTemporaryFile.rollover() — момент, когда данные уезжают на диск.
    Со стандартным порогом Starlette (1 МБ) файл на 3 МБ туда бы уехал."""
    def fail(self):
        raise AssertionError("загрузка записана во временный файл на диске")

    monkeypatch.setattr(tempfile.SpooledTemporaryFile, "rollover", fail)
    big_chat = DEMO * 15  # ~3 МБ
    assert len(big_chat) > 1024 * 1024 * 2
    assert upload(big_chat).status_code == 200


def test_cors_only_for_local_frontend():
    allowed = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    foreign = client.get("/api/health", headers={"Origin": "https://example.com"})
    assert "access-control-allow-origin" not in foreign.headers
