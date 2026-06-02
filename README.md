# SDVX B50 Server

FastAPI server for storing SDVX B50 uploads from the desktop tool.

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

### Fetch B50 from Maomani

```http
POST /api/sdvx/b50/providers/maomani
Content-Type: application/json
```

Request:

```json
{
  "cardNo": "E004B2A9A40593F8"
}
```

The provider queries `maomani.cn:573`, converts SDVX 7 score records to a B50
payload, and returns the same short clear-lamp labels used by uploaded B50 data
(`ND`, `C`, `EC`, `HC`, `MC`, `UC`, `PUC`). Song metadata fields that require a
local music database are returned as empty strings; use `difficultyNum` with the
client's local music database to resolve title, difficulty label, and level.

Disable this provider with:

```bash
ENABLE_MAOMANI_PROVIDER=0 .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```
