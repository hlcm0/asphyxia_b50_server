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
