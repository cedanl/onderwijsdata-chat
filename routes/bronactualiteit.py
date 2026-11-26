from fastapi import APIRouter

from core import bronactualiteit_overzicht

router = APIRouter(tags=["bronactualiteit"])


@router.get("/api/bronactualiteit")
def get_bronactualiteit():
    """Per bron en dataset hoe actueel ze is (#1266): laatste periode, laatste wijziging, status, frequentie en een
    verwachte volgende editie alleen als de bron die noemt. Uit de catalogus, zonder verzoek naar een bron; een bron die
    niet antwoordt staat er als "niet bereikbaar". Openbaar, net als /api/bronstatus: het is metadata van open bronnen."""
    return bronactualiteit_overzicht.overzicht()
