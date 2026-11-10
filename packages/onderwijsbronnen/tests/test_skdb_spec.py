"""De openbare OpenAPI-spec van de Studiekeuzedatabase tegen wat het pakket leest (#878): zonder sleutel, zonder netwerk.

De bron-ping van de chat haalt de spec dagelijks op; hier staat de toets op een minimale synthetische spec
(`proefbestand.openapi`) met alleen de paden en veldnamen die het pakket nodig heeft.
"""

from __future__ import annotations

import httpx
import pytest

from onderwijsbronnen import skdb
from onderwijsbronnen.skdb import proefbestand, schemakaart, spec

SLEUTEL = "geheime-proefsleutel"


def test_de_minimale_spec_heeft_alles_wat_het_pakket_leest():
    assert spec.ontbreekt(proefbestand.openapi()) == []


def test_de_getoetste_tabellen_zijn_de_tabellen_van_de_zes_overzichten():
    """Uit de code, niet met de hand: een overzicht dat een tabel gaat lezen, komt vanzelf in de ping."""
    verwacht = {t for t, m in schemakaart.MOGELIJKHEDEN.items() if m.soort == schemakaart.OVERZICHT}
    assert set(spec.tabellen()) == verwacht
    assert len(verwacht) == 9
    assert set(spec.GENEST) <= verwacht  # geen dode regel in de kaart naar de geneste velden


def test_een_tabel_zonder_pad_wordt_genoemd():
    s = proefbestand.openapi()
    del s["paths"]["/doorstroommbohbo"]
    assert spec.ontbreekt(s) == ["tabel doorstroommbohbo: geen pad dat eindigt op /doorstroommbohbo"]


def test_een_tabel_op_een_dieper_pad_telt_mee():
    """`lotingopleidingendecentraleselecties` hangt onder een instelling, niet in de wortel."""
    s = proefbestand.openapi()
    assert "/instellingen/{instellingSkdb}/lotingopleidingendecentraleselecties" in s["paths"]
    del s["paths"]["/instellingen/{instellingSkdb}/lotingopleidingendecentraleselecties"]
    assert spec.ontbreekt(s) == [
        "tabel lotingopleidingendecentraleselecties: geen pad dat eindigt op /lotingopleidingendecentraleselecties"
    ]


def test_een_geneste_tabel_zonder_veld_wordt_genoemd_met_veld_en_pad():
    s = proefbestand.openapi()
    del s["paths"]["/studies"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["items"][
        "properties"
    ]["doorstroomBachelorMaster"]
    assert spec.ontbreekt(s) == [
        "tabel doorstroombachelormaster: geen veld doorstroomBachelorMaster in het antwoord van /studies"
    ]


def test_een_geneste_tabel_zonder_pad_noemt_het_pad():
    s = proefbestand.openapi()
    del s["paths"]["/standaardonderwijsindeling"]
    assert spec.ontbreekt(s) == [
        "tabel standaardonderwijsindelingvorm: geen pad /standaardonderwijsindeling in de spec"
    ]


def test_zonder_export_of_zonder_zip_een_melding():
    s = proefbestand.openapi()
    del s["paths"]["/export/json"]
    assert spec.ontbreekt(s) == ["geen pad /export/json in de spec"]

    s = proefbestand.openapi()
    s["paths"]["/export/json"]["get"]["responses"]["200"]["content"] = {"application/json": {}}
    assert spec.ontbreekt(s) == ["/export/json levert geen application/zip meer (wel: application/json)"]


def test_een_lokale_ref_wordt_gevolgd():
    """Zet LCSK een schema in `components`, dan is dat geen wijziging van de API."""
    s = proefbestand.openapi()
    antwoord = s["paths"]["/opleidingen"]["get"]["responses"]["200"]["content"]["application/json"]
    s["components"] = {"schemas": {"opleiding": antwoord["schema"]["items"]}}
    antwoord["schema"]["items"] = {"$ref": "#/components/schemas/opleiding"}
    assert spec.ontbreekt(s) == []


def test_een_spec_zonder_paden_noemt_alles():
    gemeld = spec.ontbreekt({"openapi": "3.1.0"})
    assert len(gemeld) == 1 + len(spec.tabellen())


# --- ophalen ----------------------------------------------------------------------------------------------------


def test_de_spec_gaat_zonder_sleutel_ook_als_er_een_in_de_omgeving_staat(monkeypatch):
    """Afspraak #878 (04-11): de sleutel staat niet in CI; de ping heeft hem niet nodig en stuurt hem nooit mee."""
    monkeypatch.setenv(skdb.SLEUTEL_ENV, SLEUTEL)
    gezien = {}

    def get(url, **kwargs):
        gezien.update(url=url, **kwargs)
        return httpx.Response(200, json=proefbestand.openapi())

    monkeypatch.setattr(httpx, "get", get)
    assert spec.ontbreekt(spec.haal_spec()) == []
    assert gezien["url"] == "https://api.skdb.nl/v1/openapi.json"
    assert "Authorization" not in gezien["headers"]
    assert SLEUTEL not in repr(gezien)


@pytest.mark.parametrize("status", [404, 500])
def test_een_http_fout_is_een_skdbfout_met_de_status(monkeypatch, status):
    monkeypatch.setattr(httpx, "get", lambda *a, **k: httpx.Response(status, text="weg"))
    with pytest.raises(skdb.SkdbFout, match=f"HTTP {status}"):
        spec.haal_spec()


def test_geen_json_of_geen_object_is_een_skdbfout(monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda *a, **k: httpx.Response(200, text="<html>onderhoud</html>"))
    with pytest.raises(skdb.SkdbFout, match="geen JSON"):
        spec.haal_spec()
    monkeypatch.setattr(httpx, "get", lambda *a, **k: httpx.Response(200, json=[1, 2]))
    with pytest.raises(skdb.SkdbFout, match="geen JSON"):
        spec.haal_spec()


def test_een_netwerkfout_is_een_skdbfout(monkeypatch):
    def get(*a, **k):
        raise httpx.ConnectError("kapot")

    monkeypatch.setattr(httpx, "get", get)
    with pytest.raises(skdb.SkdbFout, match="niet bereikbaar"):
        spec.haal_spec()
