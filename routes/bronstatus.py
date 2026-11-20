from fastapi import APIRouter

from core import bronstatus

router = APIRouter(tags=["bronstatus"])


@router.get("/api/bronstatus")
async def get_bronstatus():
    """De bronnen die nu niet live zijn (#1057); een lege lijst als alles antwoordt. Openbaar, net als /api/config: de
    lijst zegt alleen of een openbare bron antwoordt, en het loginscherm mag hem ook lezen."""
    return {"niet_live": bronstatus.niet_live()}
