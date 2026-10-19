import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from app.crypto import encrypt_cloud_fields
from app.models import B50UploadRequest


DEFAULT_DATABASE_PATH = Path("data") / "b50.sqlite3"


def database_path() -> Path:
    return Path(os.environ.get("B50_DATABASE_PATH", DEFAULT_DATABASE_PATH))


def connect() -> sqlite3.Connection:
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database() -> None:
    with connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS b50_uploads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                qq TEXT NOT NULL,
                game TEXT NOT NULL,
                version INTEGER NOT NULL,
                schema_version INTEGER NOT NULL,
                player_name TEXT NOT NULL,
                sdvx_id INTEGER NOT NULL,
                total_vf TEXT NOT NULL,
                generated_at TEXT NOT NULL,
                upload_at TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_b50_uploads_latest
            ON b50_uploads (qq, game, version, id DESC)
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sdvx_players (
                qq TEXT PRIMARY KEY,
                refid TEXT NOT NULL,
                name TEXT NOT NULL,
                sdvx_id INTEGER NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        # One row per chart: the best score, EX score, clear and grade seen so far. The judgement
        # columns belong to the play that set `score` and stay NULL when that play was not captured.
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sdvx_scores (
                qq TEXT NOT NULL,
                mid INTEGER NOT NULL,
                type INTEGER NOT NULL,
                score INTEGER NOT NULL,
                exscore INTEGER NOT NULL,
                clear INTEGER NOT NULL,
                grade INTEGER NOT NULL,
                volforce INTEGER NOT NULL,
                button_rate INTEGER NOT NULL,
                long_rate INTEGER NOT NULL,
                vol_rate INTEGER NOT NULL,
                title TEXT,
                difficulty_label TEXT,
                difnum INTEGER,
                max_chain INTEGER,
                s_critical INTEGER,
                critical INTEGER,
                near INTEGER,
                error INTEGER,
                best_played_at TEXT,
                play_count INTEGER NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (qq, mid, type)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sdvx_plays (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                qq TEXT NOT NULL,
                uid TEXT NOT NULL,
                mid INTEGER NOT NULL,
                type INTEGER NOT NULL,
                score INTEGER NOT NULL,
                exscore INTEGER NOT NULL,
                clear INTEGER NOT NULL,
                grade INTEGER NOT NULL,
                max_chain INTEGER NOT NULL,
                s_critical INTEGER NOT NULL,
                critical INTEGER NOT NULL,
                near INTEGER NOT NULL,
                error INTEGER NOT NULL,
                played_at TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                UNIQUE (qq, uid)
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_sdvx_plays_chart
            ON sdvx_plays (qq, mid, type, id DESC)
            """
        )


def insert_upload(payload: B50UploadRequest) -> int:
    payload_json = encrypt_cloud_fields(payload.model_dump_json())
    with connect() as connection:
        cursor = connection.execute(
            """
            INSERT INTO b50_uploads (
                qq,
                game,
                version,
                schema_version,
                player_name,
                sdvx_id,
                total_vf,
                generated_at,
                upload_at,
                payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.qq,
                payload.game,
                payload.version,
                payload.schemaVersion,
                payload.player.name,
                payload.player.sdvxId,
                payload.totalVf,
                payload.generatedAt,
                payload.client.uploadAt,
                payload_json,
            ),
        )
        return int(cursor.lastrowid)


def get_latest_upload(qq: str) -> dict[str, Any] | None:
    with connect() as connection:
        row = connection.execute(
            """
            SELECT payload_json
            FROM b50_uploads
            WHERE qq = ? AND game = 'sdvx' AND version = 7
            ORDER BY id DESC
            LIMIT 1
            """,
            (qq,),
        ).fetchone()

    if row is None:
        return None

    return json.loads(row["payload_json"])


def count_uploads(qq: str) -> int:
    with connect() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS upload_count
            FROM b50_uploads
            WHERE qq = ? AND game = 'sdvx' AND version = 7
            """,
            (qq,),
        ).fetchone()

    return int(row["upload_count"])
