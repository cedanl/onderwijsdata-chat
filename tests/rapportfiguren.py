"""Hulp voor tests van het rapport met figuren uit het gesprek (#993): een figuur maken zoals de chat dat doet."""

import plotly.io as pio

from agent import figuurstappen, report
from agent.report_figuren import VasteFiguren, VasteFiguur, beschrijf
from tools import dispatch


def figuur_in_gesprek(sessie: dict, tool: str, argumenten: dict) -> str:
    """Draai de tool zoals de chat en leg de stap vast zoals `run._bewaar_stap`; geeft de id van de figuur."""
    resultaat, figuur = dispatch(tool, argumenten)
    assert figuur is not None, resultaat
    figuurstappen.leg_vast(sessie, tool, argumenten, resultaat, figuur)
    return figuurstappen.figuur_id(tool, argumenten)


def vaste_figuren(monkeypatch, *figuren: tuple[str, str | None]) -> None:
    """Laat het rapport deze figuren (figure_json, data_key) als gekozen figuren uit het gesprek krijgen, zonder ze
    opnieuw te maken: voor tests van wat het rapport met zijn figuren doet."""
    vast = VasteFiguren(
        tuple(
            VasteFiguur(
                figure_json=figure_json,
                data_key=data_key or "",
                keys=(data_key,) if data_key else (),
                bewijs=beschrijf(pio.from_json(figure_json), met_titel=False),
                beschrijving=beschrijf(pio.from_json(figure_json)),
            )
            for figure_json, data_key in figuren
        )
    )

    async def maak(session, ids):
        return vast

    monkeypatch.setattr(report, "maak_figuren", maak)
