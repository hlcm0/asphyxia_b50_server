import re
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.database import count_uploads, get_latest_upload, initialize_database, insert_upload
from app.models import ApiResponse, B50UploadRequest, LatestB50Response
from app.providers.maomani.router import router as maomani_router


QQ_PATTERN = re.compile(r"^[0-9]{5,12}$")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    initialize_database()
    yield


app = FastAPI(title="SDVX B50 Server", version="1.0.0", lifespan=lifespan)

if os.environ.get("ENABLE_MAOMANI_PROVIDER", "1") == "1":
    app.include_router(maomani_router)


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


@app.get("/api/sdvx/b50/latest/{qq}", response_model=LatestB50Response)
def latest_b50(qq: str) -> LatestB50Response:
    if not QQ_PATTERN.fullmatch(qq):
        return JSONResponse(
            status_code=400,
            content={"ok": False, "message": "invalid qq"},
        )

    payload = get_latest_upload(qq)
    if payload is None:
        return JSONResponse(
            status_code=404,
            content={"ok": False, "message": "B50 data not found."},
        )

    return LatestB50Response(ok=True, message="ok", data=payload)


@app.get("/api/sdvx/b50/count/{qq}", response_model=dict[str, int | bool | str])
def upload_count(qq: str) -> dict[str, int | bool | str]:
    if not QQ_PATTERN.fullmatch(qq):
        return JSONResponse(
            status_code=400,
            content={"ok": False, "message": "invalid qq"},
        )

    return {"ok": True, "message": "ok", "count": count_uploads(qq)}
