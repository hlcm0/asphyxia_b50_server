"""Full score lists: per-chart best records, the play log, and the B50 derived from them."""

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from app.database import connect, get_latest_upload, insert_upload
from app.models import B50UploadRequest, ScorePlay, ScoreRecord, ScoreUploadRequest


# Volforce factors in hundredths, as in the desktop tool (volforce.rs).
GRADE_FACTOR = {1: 80, 2: 82, 3: 85, 4: 88, 5: 91, 6: 94, 7: 97, 8: 100, 9: 102, 10: 105}
CLEAR_FACTOR = {1: 50, 2: 100, 3: 102, 4: 104, 5: 106, 6: 110}
CLEAR_LAMP = {1: "C", 2: "EC", 3: "HC", 4: "MC", 5: "UC", 6: "PUC"}
JUDGEMENT_COLUMNS = ("max_chain", "s_critical", "critical", "near", "error")


def calculate_volforce(difnum: int, score: int, clear: int, grade: int) -> int:
    """floor(level * score / 10M * grade factor * clear factor * 20), in exact integer arithmetic."""
    numerator = difnum * score * GRADE_FACTOR.get(grade, 0) * CLEAR_FACTOR.get(clear, 0) * 20
    return numerator // (10 * 10_000_000 * 100 * 100)


def format_level(difnum: int) -> str:
    return str(difnum // 10) if difnum % 10 == 0 else f"{difnum / 10:.1f}"


def format_single_vf(volforce: int) -> str:
    return f"{volforce / 20:.2f}"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def merge_record(
    existing: dict[str, Any] | None, incoming: ScoreRecord, play: ScorePlay | None, now: str
) -> dict[str, Any]:
    """Merge one record (or one play, when `play` is set) into a chart's best record.

    Score, EX score, clear and grade each keep their best value, like the asphyxia v7 save_m handler.
    The rates and judgement counts follow the play that set the best score.
    """
    if existing is None:
        merged: dict[str, Any] = {
            "score": 0, "exscore": 0, "clear": 0, "grade": 0, "volforce": 0,
            "button_rate": 0, "long_rate": 0, "vol_rate": 0,
            "title": None, "difficulty_label": None, "difnum": None,
            "best_played_at": None, "play_count": 0,
        }
        merged.update(dict.fromkeys(JUDGEMENT_COLUMNS))
    else:
        merged = dict(existing)

    judgements = None
    if play is not None:
        judgements = (play.maxChain, play.sCritical, play.critical, play.near, play.error)
        merged["play_count"] += 1

    if incoming.score > merged["score"]:
        merged.update(
            score=incoming.score,
            button_rate=incoming.buttonRate,
            long_rate=incoming.longRate,
            vol_rate=incoming.volRate,
            best_played_at=play.playedAt if play is not None else None,
        )
        merged.update(zip(JUDGEMENT_COLUMNS, judgements or (None,) * len(JUDGEMENT_COLUMNS)))
    elif judgements is not None and incoming.score == merged["score"] and merged["critical"] is None:
        # The best score came from a snapshot; this captured play matches it.
        merged.update(zip(JUDGEMENT_COLUMNS, judgements), best_played_at=play.playedAt)

    merged["exscore"] = max(merged["exscore"], incoming.exscore)
    # SDVX 7 numbers the clear types in order (asphyxia keeps the max as well).
    merged["clear"] = max(merged["clear"], incoming.clear)
    merged["grade"] = max(merged["grade"], incoming.grade)

    for column, value in (
        ("title", incoming.title),
        ("difficulty_label", incoming.difficultyLabel),
        ("difnum", incoming.difnum),
    ):
        if value is not None:
            merged[column] = value

    if merged["difnum"] is not None:
        merged["volforce"] = calculate_volforce(
            merged["difnum"], merged["score"], merged["clear"], merged["grade"]
        )
    else:
        merged["volforce"] = max(merged["volforce"], incoming.volforce)

    if merged != existing:
        merged["updated_at"] = now
    return merged


def save_scores(payload: ScoreUploadRequest) -> tuple[int, int, bool]:
    """Store an upload. Returns (records changed, plays added, whether a new B50 row was written)."""
    now = utc_now()
    changed: set[tuple[int, int]] = set()
    plays_added = 0

    with connect() as connection:
        connection.execute(
            """
            INSERT INTO sdvx_players (qq, refid, name, sdvx_id, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (qq) DO UPDATE SET
                refid = excluded.refid,
                name = excluded.name,
                sdvx_id = excluded.sdvx_id,
                updated_at = excluded.updated_at
            """,
            (payload.qq, payload.player.refid, payload.player.name, payload.player.sdvxId, now),
        )

        for record in payload.records:
            if _merge_into_table(connection, payload.qq, record, None, now):
                changed.add((record.mid, record.type))

        for play in payload.plays:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO sdvx_plays (
                    qq, uid, mid, type, score, exscore, clear, grade,
                    max_chain, s_critical, critical, near, error, played_at, payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.qq, play.uid, play.mid, play.type, play.score, play.exscore,
                    play.clear, play.grade, play.maxChain, play.sCritical, play.critical,
                    play.near, play.error, play.playedAt, play.model_dump_json(),
                ),
            )
            if cursor.rowcount == 0:
                continue  # already stored by an earlier (retried) upload
            plays_added += 1
            if _merge_into_table(connection, payload.qq, play, play, now):
                changed.add((play.mid, play.type))

        b50 = build_b50(connection, payload)

    b50_updated = False
    if b50 is not None and _b50_differs(b50, get_latest_upload(payload.qq)):
        insert_upload(b50)
        b50_updated = True
    return len(changed), plays_added, b50_updated


def _merge_into_table(
    connection: sqlite3.Connection, qq: str, record: ScoreRecord, play: ScorePlay | None, now: str
) -> bool:
    row = connection.execute(
        "SELECT * FROM sdvx_scores WHERE qq = ? AND mid = ? AND type = ?",
        (qq, record.mid, record.type),
    ).fetchone()
    existing = None
    if row is not None:
        existing = dict(row)
        for key in ("qq", "mid", "type"):
            existing.pop(key)
    merged = merge_record(existing, record, play, now)
    if merged == existing:
        return False

    columns = ["qq", "mid", "type", *merged]
    connection.execute(
        f"INSERT OR REPLACE INTO sdvx_scores ({', '.join(columns)}) VALUES ({', '.join('?' * len(columns))})",
        (qq, record.mid, record.type, *merged.values()),
    )
    return True


def build_b50(connection: sqlite3.Connection, payload: ScoreUploadRequest) -> B50UploadRequest | None:
    """The B50 of the stored records, ranked like the desktop tool (volforce, score, mid, type)."""
    rows = connection.execute(
        """
        SELECT * FROM sdvx_scores
        WHERE qq = ? AND score > 0 AND difnum IS NOT NULL AND title IS NOT NULL
        ORDER BY volforce DESC, score DESC, mid, type
        LIMIT 50
        """,
        (payload.qq,),
    ).fetchall()
    if not rows:
        return None
    score_count = connection.execute(
        "SELECT COUNT(*) FROM sdvx_scores WHERE qq = ? AND score > 0", (payload.qq,)
    ).fetchone()[0]

    cards = [
        {
            "rank": rank,
            "mid": row["mid"],
            "difficultyNum": row["type"],
            "title": row["title"],
            "difficultyLabel": row["difficulty_label"] or "",
            "level": format_level(row["difnum"]),
            "score": row["score"],
            "clearLamp": CLEAR_LAMP.get(row["clear"], "ND"),
            "singleVf": format_single_vf(row["volforce"]),
        }
        for rank, row in enumerate(rows, start=1)
    ]
    total_vf = sum(row["volforce"] for row in rows) / 1000
    return B50UploadRequest(
        schemaVersion=1,
        game="sdvx",
        version=7,
        qq=payload.qq,
        player={**payload.player.model_dump(), "scoreCount": score_count},
        totalVf=f"{total_vf:.3f}",
        generatedAt=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        cards=cards,
        client=payload.client,
    )


def _b50_differs(b50: B50UploadRequest, latest: dict[str, Any] | None) -> bool:
    """Every b50_uploads row is kept, so only write one when the picture would change
    (scoreCount is not drawn and changes with every new chart)."""
    if latest is None:
        return True
    new = b50.model_dump()
    old_player = {**(latest.get("player") or {}), "scoreCount": new["player"]["scoreCount"]}
    return new["player"] != old_player or any(
        new[key] != latest.get(key) for key in ("totalVf", "cards")
    )


def get_scores(qq: str, mid: int | None = None, chart_type: int | None = None) -> dict[str, Any] | None:
    with connect() as connection:
        player = connection.execute(
            "SELECT refid, name, sdvx_id, updated_at FROM sdvx_players WHERE qq = ?", (qq,)
        ).fetchone()
        if player is None:
            return None
        query = "SELECT * FROM sdvx_scores WHERE qq = ?"
        params: list[Any] = [qq]
        if mid is not None:
            query += " AND mid = ?"
            params.append(mid)
        if chart_type is not None:
            query += " AND type = ?"
            params.append(chart_type)
        rows = connection.execute(query + " ORDER BY mid, type", params).fetchall()

    return {
        "player": {
            "refid": player["refid"],
            "name": player["name"],
            "sdvxId": player["sdvx_id"],
            "updatedAt": player["updated_at"],
        },
        "records": [_record_json(row) for row in rows],
    }


def _record_json(row: sqlite3.Row) -> dict[str, Any]:
    judgements = None
    if row["critical"] is not None:
        judgements = {
            "maxChain": row["max_chain"],
            "sCritical": row["s_critical"],
            "critical": row["critical"],
            "near": row["near"],
            "error": row["error"],
        }
    return {
        "mid": row["mid"],
        "type": row["type"],
        "title": row["title"],
        "difficultyLabel": row["difficulty_label"],
        "level": format_level(row["difnum"]) if row["difnum"] is not None else None,
        "difnum": row["difnum"],
        "score": row["score"],
        "exscore": row["exscore"],
        "clear": row["clear"],
        "clearLamp": CLEAR_LAMP.get(row["clear"], "ND"),
        "grade": row["grade"],
        "volforce": row["volforce"],
        "singleVf": format_single_vf(row["volforce"]),
        "buttonRate": row["button_rate"],
        "longRate": row["long_rate"],
        "volRate": row["vol_rate"],
        "judgements": judgements,
        "bestPlayedAt": row["best_played_at"],
        "playCount": row["play_count"],
        "updatedAt": row["updated_at"],
    }


def get_plays(
    qq: str, mid: int | None = None, chart_type: int | None = None, limit: int = 50
) -> list[dict[str, Any]]:
    query = "SELECT id, payload_json, created_at FROM sdvx_plays WHERE qq = ?"
    params: list[Any] = [qq]
    if mid is not None:
        query += " AND mid = ?"
        params.append(mid)
    if chart_type is not None:
        query += " AND type = ?"
        params.append(chart_type)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    with connect() as connection:
        rows = connection.execute(query, params).fetchall()
    return [
        {**json.loads(row["payload_json"]), "id": row["id"], "receivedAt": row["created_at"]}
        for row in rows
    ]
