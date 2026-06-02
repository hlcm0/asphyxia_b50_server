from collections.abc import Iterator
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch) -> Iterator[TestClient]:
    monkeypatch.setenv("B50_DATABASE_PATH", str(tmp_path / "b50.sqlite3"))
    with TestClient(app) as test_client:
        yield test_client


def upload_payload() -> dict:
    return {
        "schemaVersion": 1,
        "game": "sdvx",
        "version": 7,
        "qq": "123456789",
        "player": {
            "refid": "REFID",
            "name": "PLAYER",
            "sdvxId": 12345678,
            "scoreCount": 300,
        },
        "totalVf": "19.123",
        "generatedAt": "2026-06-01 12:34",
        "cards": [
            {
                "rank": 1,
                "mid": 1001,
                "title": "Song A",
                "difficultyLabel": "MXM",
                "level": "19",
                "score": 9999000,
                "clearLamp": "UC",
                "singleVf": "0.500",
                "jacketPath": "data:image/png;base64,ignored",
            }
        ],
        "client": {
            "app": "sdvx-b50-tool",
            "uploadAt": "2026-06-01T12:35:00Z",
        },
    }


def test_health(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "message": "ok"}


def test_uploads_are_retained_and_latest_returns_newest(client: TestClient) -> None:
    first = upload_payload()
    second = deepcopy(first)
    second["totalVf"] = "20.000"
    second["cards"][0]["title"] = "Song B"
    second["cards"][0]["score"] = 10_000_000
    second["client"]["uploadAt"] = "2026-06-01T12:36:00Z"

    assert client.post("/api/sdvx/b50", json=first).status_code == 200
    assert client.post("/api/sdvx/b50", json=second).status_code == 200

    count_response = client.get("/api/sdvx/b50/count/123456789")
    latest_response = client.get("/api/sdvx/b50/latest/123456789")

    assert count_response.json() == {"ok": True, "message": "ok", "count": 2}
    assert latest_response.status_code == 200
    latest = latest_response.json()["data"]
    assert latest["totalVf"] == "20.000"
    assert latest["cards"][0]["title"] == "Song B"
    assert "jacketPath" not in latest["cards"][0]


def test_latest_returns_404_for_missing_qq(client: TestClient) -> None:
    response = client.get("/api/sdvx/b50/latest/123456789")

    assert response.status_code == 404
    assert response.json() == {"ok": False, "message": "B50 data not found."}


def test_invalid_qq_returns_400(client: TestClient) -> None:
    response = client.get("/api/sdvx/b50/latest/not-a-qq")

    assert response.status_code == 400
    assert response.json() == {"ok": False, "message": "invalid qq"}


def test_invalid_upload_body_returns_422(client: TestClient) -> None:
    payload = upload_payload()
    payload["cards"] = []

    response = client.post("/api/sdvx/b50", json=payload)

    assert response.status_code == 422
    assert response.json() == {"ok": False, "message": "invalid request body"}


def test_maomani_route_returns_provider_b50(client: TestClient, monkeypatch) -> None:
    def fake_fetch(card_no: str) -> dict:
        assert card_no == "E004B2A9A40593F8"
        return {
            "schemaVersion": 2,
            "source": "maomani",
            "game": "sdvx",
            "version": 7,
            "player": {"refid": "REFID", "name": "", "sdvxId": 0, "scoreCount": 1},
            "totalVf": "0.500",
            "generatedAt": "2026-06-02T00:00:00+00:00",
            "cards": [
                {
                    "rank": 1,
                    "mid": 1001,
                    "difficultyNum": 4,
                    "title": "",
                    "difficultyLabel": "",
                    "level": "",
                    "score": 10_000_000,
                    "clearLamp": "PUC",
                    "singleVf": "0.50",
                }
            ],
        }

    monkeypatch.setattr("app.providers.maomani.router.fetch_b50_by_card", fake_fetch)

    response = client.post(
        "/api/sdvx/b50/providers/maomani",
        json={"cardNo": "E004B2A9A40593F8"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["data"]["source"] == "maomani"
    assert body["data"]["cards"][0]["difficultyNum"] == 4
