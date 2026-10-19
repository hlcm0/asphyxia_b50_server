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

Returns the newest uploaded B50 payload for the given QQ number. Add `?game=sdvx-plus&version=6` (or any
other supported game, see below) for that game's B50; the default is `game=sdvx&version=7`. The same
parameters work on `/api/sdvx/b50/count/{qq}`.

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

Stores a player's full score list, keyed by QQ, game, version, mid and chart type (0 NOV … 5 ULT).

Supported `game` / `version` pairs, each stored separately with its own B50:

| game | version | |
|---|---|---|
| `sdvx` | 7 | SOUND VOLTEX ∇ |
| `sdvx` | 6 | SOUND VOLTEX EXCEED GEAR |
| `sdvx-plus` | 6 | SOUND VOLTEX PLUS (EXCEED GEAR with custom charts; its music ids are different songs) |

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
- `difnum` is the level times 10 (185 = 18.5). With it the server computes the chart's volforce; without it
  the game's `volforce` is kept and the chart is left out of the B50. Volforce is
  floor(level × score / 10M × grade × clear × 20): version 7 uses the desktop tool's factors, version 6 the
  EXCEED GEAR ones (UC 1.05 instead of 1.06).
- `clear` is sent as the game numbers it. Version 6 clear types (4 UC, 5 PUC, 6 MAXXIVE) are converted to
  the version 7 order (4 MAXXIVE, 5 UC, 6 PUC) on arrival; a converted play keeps the original as `clearRaw`.
- Plays are deduplicated by `uid`, so a client can safely resend after a failure.
- After every upload the B50 is rebuilt from the stored records. When it differs from the latest one, it is
  written to `b50_uploads`, so `GET /api/sdvx/b50/latest/{qq}` returns it.

The response reports how many charts changed, how many plays were new, and whether a new B50 was written:

```json
{"ok": true, "message": "ok", "records": 1, "plays": 1, "b50Updated": true}
```

### Get Scores by QQ

```http
GET /api/sdvx/scores/{qq}?game=sdvx&version=7&mid=1001&type=4
```

Returns `{"game", "version", "player": …, "records": […]}`. `mid` and `type` are optional filters. Each record has the stored
fields plus `level`, `clearLamp`, `singleVf`, `judgements` (or `null`), `bestPlayedAt` and `playCount`.

### Get Plays by QQ

```http
GET /api/sdvx/plays/{qq}?game=sdvx&version=7&mid=1001&type=4&limit=50
```

Returns `{"plays": […]}`, newest first, as uploaded plus `id` and `receivedAt`. `limit` is 1 to 500. `game`
and `version` default to `sdvx` and 7 on both endpoints.
