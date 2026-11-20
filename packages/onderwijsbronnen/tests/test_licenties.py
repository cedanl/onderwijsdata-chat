"""De onderwijslicenties van een instelling in RIO v3 (#1060), zonder netwerk.

De fixture bevriest wat RIO op 19-11-2026 gaf voor Avans (07GR): de licenties op de DUO-peildatum 2025-10-01 (58) en
op 2026-11-19 (62), ingekort tot id, data en de link naar de opleidingserkenning, plus de erkenningen van de zes
licenties die tussen die dagen wisselden. Informatica (34479) verdween per 2026-09-01; HBO-ICT (30020) kwam erbij.
"""

import datetime as dt
import json
from pathlib import Path

import httpx
import pytest
from onderwijsbronnen.rio import Licentie, client, licenties, met_erkenning, onderwijslicenties

_RIO = json.loads((Path(__file__).parent / "fixtures" / "rio_onderwijslicenties_07gr.json").read_text())
_PEIL, _NU = "2025-10-01", "2026-11-19"


@pytest.fixture
def rio(monkeypatch):
    aanroepen: list[tuple[str, dict]] = []

    def related(resource, id, sub, **params):
        aanroepen.append((f"{resource}/{id}/{sub}", params))
        return list(_RIO.get(params["datumGeldigOp"], [])) if id == "07GR" else []

    def link(href):
        aanroepen.append((href, {}))
        return _RIO["opleidingserkenningen"][href]

    monkeypatch.setattr(licenties, "related", related)
    monkeypatch.setattr(licenties, "link", link)
    return aanroepen


def test_avans_heeft_58_licenties_op_de_peildatum_en_62_vandaag(rio):
    assert len(onderwijslicenties("07GR", _PEIL)) == 58
    assert len(onderwijslicenties("07GR", dt.date(2026, 11, 19))) == 62
    assert [params for _, params in rio] == [{"datumGeldigOp": _PEIL}, {"datumGeldigOp": _NU}]


def test_zonder_peildatum_vraagt_het_de_stand_van_vandaag(rio):
    onderwijslicenties("07GR")
    assert rio == [("erkenningen/07GR/onderwijslicenties", {"datumGeldigOp": dt.date.today().isoformat()})]


def test_een_licentie_heeft_nog_geen_opleidingscode(rio):
    eerste = onderwijslicenties("07GR", _PEIL)[0]
    assert eerste.croho is None and eerste.onderdeel is None
    assert eerste.erkenning and eerste.erkenning.endswith(f"/opleidingserkenning?datumGeldigOp={_PEIL}")


def test_tussen_de_peildatum_en_vandaag_verdween_informatica_en_kwamen_er_vijf_bij(rio):
    toen = {lic.id: lic for lic in onderwijslicenties("07GR", _PEIL)}
    nu = {lic.id: lic for lic in onderwijslicenties("07GR", _NU)}
    weg = [met_erkenning(toen[i]) for i in toen.keys() - nu.keys()]
    nieuw = sorted((met_erkenning(nu[i]) for i in nu.keys() - toen.keys()), key=lambda lic: lic.croho or "")

    assert [(lic.croho, lic.onderdeel, lic.einddatum, lic.instroom_einddatum) for lic in weg] == [
        ("34479", "TECHNIEK", "2026-09-01", "2026-09-01")
    ]
    assert [(lic.croho, lic.onderdeel, lic.begindatum) for lic in nieuw] == [
        ("30020", "TECHNIEK", "2026-09-01"),
        ("45534", "GEDRAG_EN_MAATSCHAPPIJ", "2026-09-01"),
        ("49512", "SECTOROVERSTIJGEND", "2026-09-01"),
        ("49513", "SECTOROVERSTIJGEND", "2026-09-01"),
        ("49514", "SECTOROVERSTIJGEND", "2026-09-01"),
    ]


def test_een_onbekende_erkenning_heeft_geen_licenties(rio):
    assert onderwijslicenties("99XX", _PEIL) == ()


def test_een_licentie_zonder_link_blijft_zoals_ze_is(rio):
    zonder = Licentie("x", "2020-09-01", None, None)
    assert met_erkenning(zonder) is zonder
    assert rio == []


class _Antwoord:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        return None

    def json(self):
        return self._data


def test_related_volgt_de_next_links_zonder_page_parameter(monkeypatch):
    """`onderwijslicenties` kent geen `page` (HTTP 400): de tweede pagina komt alleen via de next-link."""
    basis = f"{client.BASE_URL}/erkenningen/07GR/onderwijslicenties"
    volgende = f"{basis}?datumGeldigOp={_PEIL}&cursor=2"
    paginas = {
        basis: {"_embedded": {"Onderwijslicenties": [{"id": "a"}]}, "_links": {"next": {"href": volgende}}},
        volgende: {"_embedded": {"Onderwijslicenties": [{"id": "b"}]}, "_links": {}},
    }
    aanroepen = []

    def get(url, timeout, params=None):
        aanroepen.append((url, params))
        return _Antwoord(paginas[url])

    monkeypatch.setattr(httpx, "get", get)
    assert client.related("erkenningen", "07GR", "onderwijslicenties", datumGeldigOp=_PEIL) == [
        {"id": "a"},
        {"id": "b"},
    ]
    assert aanroepen == [(basis, {"datumGeldigOp": _PEIL}), (volgende, None)]


def test_link_vraagt_de_href_zoals_rio_hem_gaf(monkeypatch):
    aanroepen = []
    monkeypatch.setattr(httpx, "get", lambda url, timeout: aanroepen.append(url) or _Antwoord({"id": "e"}))
    href = f"{client.BASE_URL}/onderwijslicenties/x/opleidingserkenning?datumGeldigOp={_PEIL}"
    assert client.link(href) == {"id": "e"}
    assert aanroepen == [href]


def test_een_link_buiten_de_rio_api_wordt_niet_gevolgd(monkeypatch):
    """De link komt uit een antwoord van RIO; de client volgt hem alleen naar de RIO-API zelf (#1060)."""
    import httpx
    import pytest
    from onderwijsbronnen.rio import client

    def nooit(*a, **k):
        raise AssertionError("geen verzoek")

    monkeypatch.setattr(httpx, "get", nooit)
    with pytest.raises(ValueError, match="buiten"):
        client.link("https://elders.example/api/rio/v3/opleidingserkenningen/x")
