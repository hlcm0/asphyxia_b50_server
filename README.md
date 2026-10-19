# SDVX B50 Server

FastAPI server for storing SDVX B50 uploads from the desktop tool, and full score lists with a play log.

## Setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

## Run

```bash
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The SQLite database is created automatically at:

```text
data/b50.sqlite3
```

Override the database path with:

```bash
B50_DATABASE_PATH=/path/to/b50.sqlite3 .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## API

### Health Check

```http
GET /health
```

### Upload B50

```http
POST /api/sdvx/b50
Content-Type: application/json
```

Each upload inserts a new row into `b50_uploads`; older uploads are preserved.

### Get Latest B50 by QQ

```http
GET /api/sdvx/b50/latest/{qq}
```

Returns the newest uploaded B50 payload for the given QQ number.

### Count Uploads by QQ

```http
GET /api/sdvx/b50/count/{qq}
```

This is useful for verifying that upload history is being retained.

### Upload Scores

```http
POST /api/sdvx/scores
Content-Type: application/json
```

Stores a player's full score list, keyed by QQ, mid and chart type (0 NOV … 5 ULT).

```json
{
  "schemaVersion": 1, "game": "sdvx", "version": 7, "qq": "123456789",
  "player": {"refid": "…", "name": "PLAYER", "sdvxId": 12345678},
  "records": [{"mid": 1001, "type": 4, "score": 9900000, "exscore": 3000, "clear": 5, "grade": 9,
               "buttonRate": 0, "longRate": 0, "volRate": 0, "volforce": 0,
               "title": "Song A", "difficultyLabel": "MXM", "difnum": 185}],
  "plays": [{"uid": "unique-per-play", "playedAt": "2026-10-19T12:00:00Z",
             "mid": 1001, "type": 4, "score": 9950000, "…": "same fields as records",
             "maxChain": 1500, "sCritical": 1200, "critical": 1480, "near": 15, "error": 5}],
  "client": {"app": "score_forward", "uploadAt": "2026-10-19T12:00:00Z"}
}
```

- `records` are best records as the game server holds them (for example the whole `sv7_load_m` list at card-in).
  `plays` are single played tracks (`sv7_save_m`); any extra track fields are kept with the play.
  At least one of the two lists must be non-empty.
- Each chart keeps its best score, EX score, clear and grade. The rates and judgement counts come from the
  play that set the best score; they are `null` when that play only arrived as a record.
- `difnum` is the `music_db.xml` level times 10. With it the server computes the chart's volforce like the
  desktop tool; without it the game's `volforce` is kept and the chart is left out of the B50.
- Plays are deduplicated by `uid`, so a client can safely resend after a failure.
- After every upload the B50 is rebuilt from the stored records. When it differs from the latest one, it is
  written to `b50_uploads`, so `GET /api/sdvx/b50/latest/{qq}` returns it.

The response reports how many charts changed, how many plays were new, and whether a new B50 was written:

```json
{"ok": true, "message": "ok", "records": 1, "plays": 1, "b50Updated": true}
```

### Get Scores by QQ

```http
GET /api/sdvx/scores/{qq}?mid=1001&type=4
```

Returns `{"player": …, "records": […]}`. `mid` and `type` are optional filters. Each record has the stored
fields plus `level`, `clearLamp`, `singleVf`, `judgements` (or `null`), `bestPlayedAt` and `playCount`.

### Get Plays by QQ

```http
GET /api/sdvx/plays/{qq}?mid=1001&type=4&limit=50
```

Returns `{"plays": […]}`, newest first, as uploaded plus `id` and `receivedAt`. `limit` is 1 to 500.
