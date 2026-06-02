from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.models import LatestB50Response
from app.providers.maomani.client import MaomaniClientError
from app.providers.maomani.models import MaomaniB50Request
from app.providers.maomani.service import fetch_b50_by_card


router = APIRouter(prefix="/api/sdvx/b50/providers/maomani", tags=["maomani"])


@router.post("", response_model=LatestB50Response)
def maomani_b50(payload: MaomaniB50Request) -> LatestB50Response:
    card_no = payload.cardNo.strip()
    if not card_no:
        return JSONResponse(
            status_code=400,
            content={"ok": False, "message": "cardNo is required"},
        )

    try:
        data = fetch_b50_by_card(card_no)
    except MaomaniClientError as error:
        return JSONResponse(
            status_code=502,
            content={"ok": False, "message": str(error)},
        )
    except Exception as error:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "message": f"maomani provider failed: {error}"},
        )

    return LatestB50Response(ok=True, message="ok", data=data)
