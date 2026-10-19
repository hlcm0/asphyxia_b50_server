from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.scores import calculate_volforce


QQ = "123456789"


@pytest.fixture()
def client(tmp_path, monkeypatch) -> Iterator[TestClient]:
    monkeypatch.setenv("B50_DATABASE_PATH", str(tmp_path / "b50.sqlite3"))
    with TestClient(app) as test_client:
        yield test_client


def record(mid: int, chart_type: int = 4, score: int = 9_900_000, **fields) -> dict:
    return {
        "mid": mid,
        "type": chart_type,
        "score": score,
        "exscore": 3000,
        "clear": 3,
        "grade": 9,
        "buttonRate": 100,
        "longRate": 200,
        "volRate": 300,
        "volforce": 1,
        "title": f"Song {mid}",
        "difficultyLabel": "MXM",
        "difnum": 180,
        **fields,
    }


def play(uid: str, mid: int, chart_type: int = 4, score: int = 9_950_000, **fields) -> dict:
    return {
        **record(mid, chart_type, score),
        "uid": uid,
        "playedAt": "2026-10-19T12:00:00Z",
        "maxChain": 1500,
        "sCritical": 1200,
        "critical": 1480,
        "near": 15,
        "error": 5,
        "judge": [1, 2, 3, 4, 5, 6, 7],
        "mode": 0,
        **fields,
    }


def upload(records: list[dict] = (), plays: list[dict] = ()) -> dict:
    return {
        "schemaVersion": 1,
        "game": "sdvx",
        "version": 7,
        "qq": QQ,
        "player": {"refid": "REFID", "name": "PLAYER", "sdvxId": 12345678},
        "records": list(records),
        "plays": list(plays),
        "client": {"app": "score_forward", "uploadAt": "2026-10-19T12:00:00Z"},
    }


def scores(client: TestClient, **params) -> list[dict]:
    response = client.get(f"/api/sdvx/scores/{QQ}", params=params)
    assert response.status_code == 200
    return response.json()["data"]["records"]


def test_volforce_matches_known_values() -> None:
    assert calculate_volforce(200, 10_000_000, 6, 10) == 462  # 20 PUC S
    assert calculate_volforce(185, 9_900_000, 5, 9) == 396
    assert calculate_volforce(180, 9_000_000, 0, 9) == 0  # no clear factor


def test_snapshot_builds_b50_once(client: TestClient) -> None:
    body = upload([record(1, score=9_000_000), record(2, score=9_950_000), record(3, difnum=None)])

    first = client.post("/api/sdvx/scores", json=body).json()
    second = client.post("/api/sdvx/scores", json=body).json()

    assert first == {"ok": True, "message": "ok", "records": 3, "plays": 0, "b50Updated": True}
    assert second == {"ok": True, "message": "ok", "records": 0, "plays": 0, "b50Updated": False}
    assert client.get(f"/api/sdvx/b50/count/{QQ}").json()["count"] == 1

    b50 = client.get(f"/api/sdvx/b50/latest/{QQ}").json()["data"]
    assert [card["mid"] for card in b50["cards"]] == [2, 1]  # no difnum: stored but not ranked
    assert b50["cards"][0] == {
        "rank": 1,
        "mid": 2,
        "difficultyNum": 4,
        "title": "Song 2",
        "difficultyLabel": "MXM",
        "level": "18",
        "score": 9_950_000,
        "clearLamp": "HC",
        "singleVf": "18.60",  # 18 * 0.995 * 1.02 (S) * 1.02 (HC) * 20 = 372
    }
    assert b50["player"]["scoreCount"] == 3
    assert b50["totalVf"] == "0.709"  # 372 + 337
    assert len(scores(client)) == 3


def test_play_sets_best_and_judgements_and_is_deduplicated(client: TestClient) -> None:
    client.post("/api/sdvx/scores", json=upload([record(1)]))

    body = upload(plays=[play("play-0001", 1)])
    first = client.post("/api/sdvx/scores", json=body).json()
    again = client.post("/api/sdvx/scores", json=body).json()

    assert (first["records"], first["plays"], first["b50Updated"]) == (1, 1, True)
    assert (again["records"], again["plays"], again["b50Updated"]) == (0, 0, False)
    [best] = scores(client)
    assert best["score"] == 9_950_000
    assert best["judgements"] == {
        "maxChain": 1500, "sCritical": 1200, "critical": 1480, "near": 15, "error": 5,
    }
    assert best["bestPlayedAt"] == "2026-10-19T12:00:00Z"
    assert best["playCount"] == 1

    plays = client.get(f"/api/sdvx/plays/{QQ}", params={"mid": 1}).json()["data"]["plays"]
    assert len(plays) == 1
    assert plays[0]["uid"] == "play-0001"
    assert plays[0]["judge"] == [1, 2, 3, 4, 5, 6, 7]  # extra track fields are kept


def test_worse_play_keeps_best_but_raises_other_bests(client: TestClient) -> None:
    client.post("/api/sdvx/scores", json=upload(plays=[play("play-0001", 1)]))
    worse = play("play-0002", 1, score=9_800_000, clear=5, exscore=3100, near=40)

    client.post("/api/sdvx/scores", json=upload(plays=[worse]))

    [best] = scores(client)
    assert (best["score"], best["clear"], best["exscore"]) == (9_950_000, 5, 3100)
    assert best["judgements"]["near"] == 15  # still the counts of the best-score play
    assert best["playCount"] == 2
    assert best["volforce"] == calculate_volforce(180, 9_950_000, 5, 9)
    plays = client.get(f"/api/sdvx/plays/{QQ}").json()["data"]["plays"]
    assert [p["uid"] for p in plays] == ["play-0002", "play-0001"]


def test_snapshot_judgements_follow_the_best_score(client: TestClient) -> None:
    client.post("/api/sdvx/scores", json=upload(plays=[play("play-0001", 1)]))

    client.post("/api/sdvx/scores", json=upload([record(1, score=9_950_000)]))
    assert scores(client)[0]["judgements"]["critical"] == 1480  # same score: counts kept

    client.post("/api/sdvx/scores", json=upload([record(1, score=9_990_000)]))
    best = scores(client)[0]
    assert best["score"] == 9_990_000
    assert best["judgements"] is None  # that play was not captured

    client.post("/api/sdvx/scores", json=upload(plays=[play("play-0002", 1, score=9_990_000)]))
    assert scores(client)[0]["judgements"]["critical"] == 1480  # a matching play fills them in


def test_scores_filters_and_errors(client: TestClient) -> None:
    assert client.get(f"/api/sdvx/scores/{QQ}").status_code == 404
    assert client.get("/api/sdvx/scores/abc").status_code == 400

    client.post("/api/sdvx/scores", json=upload([record(1, 3), record(1, 4), record(2, 4)]))

    assert [(r["mid"], r["type"]) for r in scores(client, mid=1)] == [(1, 3), (1, 4)]
    assert [(r["mid"], r["type"]) for r in scores(client, mid=1, type=4)] == [(1, 4)]


@pytest.mark.parametrize(
    "body",
    [
        upload(),
        upload([record(1, chart_type=6)]),
        upload([record(1, score=10_000_001)]),
        upload(plays=[play("short", 1)]),
    ],
)
def test_invalid_score_upload_returns_422(client: TestClient, body: dict) -> None:
    response = client.post("/api/sdvx/scores", json=body)

    assert response.status_code == 422
    assert response.json() == {"ok": False, "message": "invalid request body"}
