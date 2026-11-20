"""GET /api/market: which market face this visitor sees, and why."""
from fastapi import APIRouter, Header, Request, Response

from .. import marketface

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("")
async def get_market(request: Request, response: Response, market: str = "", cf_ipcountry: str | None = Header(default=None)):
    response.headers["Cache-Control"] = "no-store"
    response.headers["Vary"] = "CF-IPCountry"
    return marketface.face_payload(market, cf_ipcountry, request.app.state.settings.trust_cf_country)
