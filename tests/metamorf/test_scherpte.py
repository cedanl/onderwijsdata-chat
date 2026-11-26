"""Scherpte van de metamorfe tests (#1263): elke relatie tegen een opzettelijk kapotte variant van de tools.

Een relatie die nooit faalt, toetst niets. Per mutatie (een monkeypatch op de functie die maskeert, telt of het jaar
leest; geen bronbestand wijzigt) draaien alle relaties; minstens één moet falen. Zonder mutatie houden ze alle.
De uitkomst per mutatie staat in README.md (tabel "Scherpte") en in de MR-beschrijving van #1263.
"""

from collections.abc import Callable

import pandas as pd
import pytest

from core.sentinels import EMPTY_CELLS
from tools import query, store
from tools.canoniek import parse_filter_key

from .relaties import RELATIES


def _niet_maskeren(monkeypatch: pytest.MonkeyPatch) -> None:
    """-1 niet maskeren: de store laat de DUO-sentinel als getal staan en legt geen onderdrukte cel vast."""
    monkeypatch.setattr(store, "mask_sentinels", lambda df: (df, EMPTY_CELLS))


def _rij_dubbel_tellen(monkeypatch: pytest.MonkeyPatch) -> None:
    """Een rij dubbel tellen: de som van elke groep telt haar eerste rij twee keer."""
    echte_som = query._som_of_leeg

    def dubbel(reeks: pd.Series):
        som = echte_som(reeks)
        eerste = reeks.dropna()
        return som + eerste.iloc[0] if len(eerste) else som

    monkeypatch.setattr(query, "_som_of_leeg", dubbel)


def _een_jaar_eerder(waarde):
    if isinstance(waarde, list):
        return [_een_jaar_eerder(w) for w in waarde]
    if isinstance(waarde, int):
        return waarde - 1
    tekst = str(waarde)
    return f"{int(tekst[:4]) - 1}{tekst[4:]}" if tekst[:4].isdigit() else waarde


def _jaar_verschuiven(monkeypatch: pytest.MonkeyPatch) -> None:
    """Het jaar verschuiven: een filter op de periodekolom leest het jaar ervoor (2023 → 2022, 2023SJ00 → 2022SJ00)."""
    echte_filters = query._apply_filters

    def verschoven(df, filters, known=None, per_instelling=False):
        kolom = known.periodekolom if known else None
        filters = {k: _een_jaar_eerder(v) if parse_filter_key(k)[0] == kolom else v for k, v in filters.items()}
        return echte_filters(df, filters, known, per_instelling)

    monkeypatch.setattr(query, "_apply_filters", verschoven)


# Een relatie die in de tool al breekt (xfail met issue) zegt niets over een mutatie.
HOUDEN = [r for r in RELATIES if not r.breekt]

MUTATIES: dict[str, Callable[[pytest.MonkeyPatch], None]] = {
    "-1 niet maskeren": _niet_maskeren,
    "rij dubbel tellen": _rij_dubbel_tellen,
    "jaar verschuiven": _jaar_verschuiven,
}


def _falende_relaties() -> list[str]:
    """De relaties die falen (AssertionError); een andere fout is een kapotte mutatie en breekt de test."""
    falen = []
    for relatie in HOUDEN:
        try:
            relatie()
        except AssertionError:
            falen.append(relatie.naam)
    return falen


def test_zonder_mutatie_houdt_elke_relatie():
    assert _falende_relaties() == []


@pytest.mark.parametrize("mutatie", MUTATIES, ids=str)
def test_elke_mutatie_breekt_minstens_een_relatie(mutatie, monkeypatch, capsys):
    MUTATIES[mutatie](monkeypatch)
    falen = _falende_relaties()
    with capsys.disabled():
        print(f"\nscherpte: {mutatie!r} → {len(falen)} van {len(HOUDEN)} relaties falen: {', '.join(falen)}")
    assert falen, f"mutatie '{mutatie}': geen enkele metamorfe relatie faalt; de relaties zijn niet scherp genoeg"
