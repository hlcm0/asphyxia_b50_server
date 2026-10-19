import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.database import count_uploads, get_latest_upload, initialize_database, insert_upload
from app.models import (
    SUPPORTED_GAMES,
    ApiResponse,
    B50UploadRequest,
    DataResponse,
    LatestB50Response,
    ScoreUploadRequest,
    ScoreUploadResponse,
)
from app.scores import get_plays, get_scores, save_scores


QQ_PATTERN = re.compile(r"^[0-9]{5,12}$")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    initialize_database()
    yield


app = FastAPI(title="SDVX B50 Server", version="1.0.0", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"ok": False, "message": "invalid request body"},
    )


@app.get("/health", response_model=ApiResponse)
def health() -> ApiResponse:
    return ApiResponse(ok=True, message="ok")


@app.post("/api/sdvx/b50", response_model=ApiResponse)
def upload_b50(payload: B50UploadRequest) -> ApiResponse:
    insert_upload(payload)
    return ApiResponse(ok=True, message="Cloud upload complete.")


def _invalid_player(qq: str, game: str, version: int) -> JSONResponse | None:
    if not QQ_PATTERN.fullmatch(qq):
        return JSONResponse(
            status_code=400,
            content={"ok": False, "message": "invalid qq"},
        )
    if (game, version) not in SUPPORTED_GAMES:
        return JSONResponse(
            status_code=400,
            content={"ok": False, "message": "unsupported game and version"},
        )
    return None


@app.get("/api/sdvx/b50/latest/{qq}", response_model=LatestB50Response)
def latest_b50(qq: str, game: str = "sdvx", version: int = 7) -> LatestB50Response:
    if (error := _invalid_player(qq, game, version)) is not None:
        return error

    payload = get_latest_upload(qq, game, version)
    if payload is None:
        return JSONResponse(
            status_code=404,
            content={"ok": False, "message": "B50 data not found."},
        )

    return LatestB50Response(ok=True, message="ok", data=payload)


@app.get("/api/sdvx/b50/count/{qq}", response_model=dict[str, int | bool | str])
def upload_count(qq: str, game: str = "sdvx", version: int = 7) -> dict[str, int | bool | str]:
    if (error := _invalid_player(qq, game, version)) is not None:
        return error

    return {"ok": True, "message": "ok", "count": count_uploads(qq, game, version)}


@app.post("/api/sdvx/scores", response_model=ScoreUploadResponse)
def upload_scores(payload: ScoreUploadRequest) -> ScoreUploadResponse:
    records, plays, b50_updated = save_scores(payload)
    return ScoreUploadResponse(
        ok=True, message="ok", records=records, plays=plays, b50Updated=b50_updated
    )


@app.get("/api/sdvx/scores/{qq}", response_model=DataResponse)
def player_scores(
    qq: str,
    game: str = "sdvx",
    version: int = 7,
    mid: int | None = Query(default=None, ge=0),
    type: int | None = Query(default=None, ge=0, le=5),
) -> DataResponse:
    if (error := _invalid_player(qq, game, version)) is not None:
        return error

    data = get_scores(qq, game, version, mid, type)
    if data is None:
        return JSONResponse(
            status_code=404,
            content={"ok": False, "message": "Score data not found."},
        )

    return DataResponse(ok=True, message="ok", data=data)


@app.get("/api/sdvx/plays/{qq}", response_model=DataResponse)
def player_plays(
    qq: str,
    game: str = "sdvx",
    version: int = 7,
    mid: int | None = Query(default=None, ge=0),
    type: int | None = Query(default=None, ge=0, le=5),
    limit: int = Query(default=50, ge=1, le=500),
) -> DataResponse:
    if (error := _invalid_player(qq, game, version)) is not None:
        return error

    plays = get_plays(qq, game, version, mid, type, limit)
    return DataResponse(ok=True, message="ok", data={"plays": plays})
