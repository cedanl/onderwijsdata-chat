"""De instelling "Geavanceerd" per account (#1269): bewaard op de server, nooit afgeleid, en een echte grens.

- Standaard uit; de keuze staat onder het account in de database en geldt op elk apparaat (criterium 2).
- Ze staat in de export van "mijn gegevens" en gaat weg met "verwijder al mijn gegevens" (criterium 2); isolatie tussen
  accounts staat ook in tests/test_account_isolatie.py.
- Nooit afgeleid uit een SRAM-attribuut, de instelling of de functie, ook niet uit `settings` (criterium 3).
- De pilotlijst zet haar bij de eerste login aan, alleen voor die accounts; uit blijft uit (criterium 4; de SRAM-login
  staat in tests/test_oidc_flow.py).
- Zonder Geavanceerd telt een model dat de client meestuurt niet: de server gebruikt het standaardmodel (criterium 8).
- Beschermende uitvoer is met en zonder Geavanceerd gelijk (criterium 6, de serverkant; de weergave staat in
  frontend/src/__tests__/beschermingInvariant.test.js).

Tokens worden direct gemaakt, niet via de login: de login-limiter telt over de hele testrun mee. Waar de login zelf onder
test staat, krijgt hij een eigen limiter.
"""

import asyncio
import json
import time

import pytest
from fastapi.testclient import TestClient

from core import config, geavanceerd
from core.profiel import normaliseer_profiel
from core.pseudoniem import pseudoniem
from core.rate_limit import RateLimiter
from persistence import db
from routes import chat

_URL = "/api/mijn-gegevens/geavanceerd"
_BEVESTIGD = {"bevestig": "verwijder"}
STANDAARD = "azure_ai/standaard"
EXTRA = "azure_ai/extra"


@pytest.fixture
def client(app_client, monkeypatch):
    c = app_client(users="anna:wachtwoord-a,bert:wachtwoord-b", herlaad=("core.auth",), init_db=False)
    monkeypatch.setattr(config, "GEAVANCEERD_PILOT", frozenset())
    return c


def _token(gebruiker: str, start: int | None = None) -> str:
    from core import auth

    return auth.make_token(gebruiker, start)


def _kop(token: str | None) -> dict:
    return {"Authorization": f"Bearer {token}"} if token else {}


def _lees(client: TestClient, token: str | None):
    return client.get(_URL, headers=_kop(token))


def _zet(client: TestClient, token: str | None, body: object):
    return client.put(_URL, headers=_kop(token), json=body)


def _rij(gebruiker: str) -> dict | None:
    """De rij in de tabel, met de sleutel hier zelf afgeleid (domein `geavanceerd`), los van de code onder test."""
    with db._connection() as conn:
        rij = db._execute(
            conn, "SELECT aan, gewijzigd FROM geavanceerd WHERE sleutel = ?", (pseudoniem("geavanceerd", gebruiker),)
        ).fetchone()
    return dict(rij) if rij else None


# ── Criterium 2: bewaard per account, terug op een ander apparaat ────────────


def test_standaard_uit_zonder_een_rij(client):
    response = _lees(client, _token("anna"))

    assert response.status_code == 200
    assert response.json() == {"geavanceerd": False}
    assert response.headers["cache-control"] == "no-store"
    assert _rij("anna") is None


def test_een_keuze_staat_op_de_server_en_geldt_op_een_ander_apparaat(client):
    # Een eigen sessiestart: een token van dezelfde seconde is byte voor byte gelijk aan dat van de telefoon.
    laptop = _token("anna", start=int(time.time()) - 60)
    telefoon = _token("anna")
    assert laptop != telefoon

    assert _zet(client, laptop, {"geavanceerd": True}).json() == {"geavanceerd": True}

    assert _lees(client, telefoon).json() == {"geavanceerd": True}
    assert (_rij("anna") or {}).get("aan") == 1

    assert _zet(client, telefoon, {"geavanceerd": False}).json() == {"geavanceerd": False}
    assert _lees(client, laptop).json() == {"geavanceerd": False}
    # Uit is een bewaarde keuze, geen ontbrekende: de rij blijft, zodat de pilotlijst haar niet terugzet.
    assert (_rij("anna") or {}).get("aan") == 0


@pytest.mark.parametrize(
    "body",
    [
        None,
        {},
        {"geavanceerd": "ja"},
        {"geavanceerd": 1},
        {"geavanceerd": None},
        {"geavanceerd": True, "username": "bert"},
    ],
    ids=["zonder body", "leeg", "tekst", "getal", "null", "met een gebruikersnaam"],
)
def test_alleen_een_echte_ja_of_nee_wordt_bewaard(client, body):
    response = _zet(client, _token("anna"), body)

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)
    assert _rij("anna") is None
    assert _rij("bert") is None


@pytest.mark.parametrize("token", [None, "onzin"], ids=["zonder token", "ongeldig token"])
def test_zonder_geldige_sessie_401_en_niets_bewaard(client, token):
    assert _lees(client, token).status_code == 401
    assert _zet(client, token, {"geavanceerd": True}).status_code == 401
    assert _rij("anna") is None


def test_zonder_login_404_dan_houdt_de_browser_de_keuze(app_client):
    """Zonder login is iedereen de gedeelde `gast`: één keuze voor alle bezoekers zou niemands keuze zijn."""
    from routes.mijn_gegevens import GEEN_EIGEN_ACCOUNT

    client = app_client()

    for response in (client.get(_URL), client.put(_URL, json={"geavanceerd": True})):
        assert response.status_code == 404
        assert response.json() == {"detail": GEEN_EIGEN_ACCOUNT}
    assert _rij("gast") is None


# ── Criterium 2: in de export en weg met "verwijder al mijn gegevens" ────────


def test_de_export_toont_de_eigen_keuze(client):
    _zet(client, _token("anna"), {"geavanceerd": True})

    export = client.get("/api/mijn-gegevens/export", headers=_kop(_token("anna"))).json()
    export_bert = client.get("/api/mijn-gegevens/export", headers=_kop(_token("bert"))).json()

    [rij] = export["geavanceerd"]
    assert rij["aan"] is True and isinstance(rij["gewijzigd"], int)
    assert export_bert["geavanceerd"] == []


def test_verwijder_al_mijn_gegevens_wist_de_keuze_van_alleen_dit_account(client):
    _zet(client, _token("anna"), {"geavanceerd": True})
    _zet(client, _token("bert"), {"geavanceerd": True})

    response = client.request("DELETE", "/api/mijn-gegevens", headers=_kop(_token("anna")), json=_BEVESTIGD)

    assert response.status_code == 200
    assert response.json()["verwijderd"]["geavanceerd"] == 1
    assert _rij("anna") is None
    # Een nieuwe sessie van Anna (na het intrekken van al haar tokens) begint weer met uit; Bert houdt zijn keuze.
    assert _lees(client, _token("anna", start=int(time.time()) + 5)).json() == {"geavanceerd": False}
    assert _lees(client, _token("bert")).json() == {"geavanceerd": True}


# ── Criterium 3: nooit afgeleid ─────────────────────────────────────────────


def test_normaliseer_profiel_laat_geavanceerd_weg():
    profiel = normaliseer_profiel({"geavanceerd": True, "functie": "Onderzoeker", "model": EXTRA})

    assert "geavanceerd" not in profiel
    assert profiel == {"functie": "Onderzoeker", "model": EXTRA}


def test_sram_attributen_instelling_en_functie_veranderen_de_keuze_niet(client):
    """Een SRAM-profiel van een "analist" (organisatie, affiliatie, instelling) en een profiel met een functie
    die op analyse lijkt, zetten niets aan; een keuze die aan staat, zetten ze ook niet uit."""
    import routes.auth

    analist = {
        "name": "Anna",
        "email": "anna@hu.nl",
        "org": "IR-specialisten",
        "institution": "hu.nl",
        "email_domein": "hu.nl",
        "geavanceerd": True,
    }
    routes.auth._store_oidc_user("anna", analist)
    assert normaliseer_profiel({"functie": "IR-specialist", "instelling": "Hogeschool Utrecht", "geavanceerd": True})
    assert _lees(client, _token("anna")).json() == {"geavanceerd": False}
    assert geavanceerd.lees("anna") is False

    _zet(client, _token("bert"), {"geavanceerd": True})
    routes.auth._store_oidc_user("bert", {"name": "Bert", "org": "Docenten", "geavanceerd": False})
    assert _lees(client, _token("bert")).json() == {"geavanceerd": True}


# ── Criterium 4: de pilotlijst, alleen bij de eerste login ───────────────────


@pytest.fixture
def wachtwoordlogin(client, monkeypatch):
    """De wachtwoordlogin van routes.auth met login aan; routes.auth las AUTH_ENABLED en USERS bij het importeren."""
    import routes.auth

    monkeypatch.setattr(routes.auth, "AUTH_ENABLED", True)
    monkeypatch.setattr(routes.auth, "USERS", {"anna": "wachtwoord-a", "bert": "wachtwoord-b"})
    monkeypatch.setattr(routes.auth, "_login_limiter", RateLimiter(max_attempts=50, window_seconds=60))
    monkeypatch.setattr(config, "GEAVANCEERD_PILOT", frozenset({"anna"}))

    def login(gebruiker: str) -> str:
        response = client.post(
            "/api/auth/login", json={"username": gebruiker, "password": f"wachtwoord-{gebruiker[0]}"}
        )
        assert response.status_code == 200
        return response.json()["token"]

    return login


def test_een_pilotaccount_heeft_geavanceerd_aan_na_de_eerste_login(client, wachtwoordlogin):
    token = wachtwoordlogin("anna")

    assert _lees(client, token).json() == {"geavanceerd": True}


def test_buiten_de_pilotlijst_blijft_het_uit_en_komt_er_geen_rij(client, wachtwoordlogin):
    token = wachtwoordlogin("bert")

    assert _lees(client, token).json() == {"geavanceerd": False}
    assert _rij("bert") is None


def test_een_pilotaccount_dat_het_uitzet_houdt_het_uit_na_de_volgende_login(client, wachtwoordlogin):
    eerste = wachtwoordlogin("anna")
    assert _zet(client, eerste, {"geavanceerd": False}).json() == {"geavanceerd": False}

    tweede = wachtwoordlogin("anna")

    assert _lees(client, tweede).json() == {"geavanceerd": False}


def test_een_fout_wachtwoord_raakt_de_pilotlijst_niet(client, wachtwoordlogin):
    response = client.post("/api/auth/login", json={"username": "anna", "password": "fout"})

    assert response.status_code == 401
    assert _rij("anna") is None


def test_de_pilotlijst_zet_niets_over_een_bestaande_keuze(client, monkeypatch):
    monkeypatch.setattr(config, "GEAVANCEERD_PILOT", frozenset({"anna"}))
    geavanceerd.zet("anna", False)

    assert geavanceerd.bij_login("anna") is False
    assert geavanceerd.lees("anna") is False
    # Alleen de naam precies zoals in de lijst; hoofdletters of een domein erbij is een ander account.
    assert geavanceerd.bij_login("Anna") is False
    assert _rij("Anna") is None


def test_de_pilotlijst_komt_uit_de_omgeving(monkeypatch):
    monkeypatch.setenv("GEAVANCEERD_PILOT", " anna@hu.nl , ,bert@uu.nl,")
    assert config._namenlijst("GEAVANCEERD_PILOT") == frozenset({"anna@hu.nl", "bert@uu.nl"})


# ── Criterium 8: zonder Geavanceerd telt de modelkeuze van de client niet ────


@pytest.fixture
def chatsessie(tmp_path, monkeypatch):
    """Een sessie van `anna` met login aan, een eigen database en een aanbod van twee modellen."""
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "chat.db"))
    db.init_db()
    monkeypatch.setattr(config, "MODEL", STANDAARD)
    monkeypatch.setattr(config, "_AVAILABLE_MODELS_RAW", f"{STANDAARD},{EXTRA}")
    monkeypatch.setattr(config, "_USER_MODELS", {})
    monkeypatch.setattr(chat, "AUTH_ENABLED", True)
    monkeypatch.setattr(chat, "_berichtlimiter", RateLimiter(max_attempts=100, window_seconds=60))

    def maak(gevraagd: object = EXTRA, **extra) -> dict:
        session = chat._new_session(username="anna")
        session["chat_settings"] = {"model": gevraagd, **extra}
        return session

    return maak


@pytest.fixture
def modellen(monkeypatch) -> list[tuple[str, str | None]]:
    """Welk model elke run krijgt, als (soort, model); de agent zelf draait niet."""
    gezien: list[tuple[str, str | None]] = []

    async def bericht(content, session, emit, model):
        gezien.append(("bericht", model))

    async def rapport(session, emit, model, **_):
        gezien.append(("rapport", model))

    monkeypatch.setattr(chat, "_process_message", bericht)
    monkeypatch.setattr(chat, "_generate_report", rapport)
    return gezien


def _actie(action: str, msg: dict, session: dict) -> None:
    async def emit(event):
        pass

    async def scenario():
        taak = await chat.ACTIES[action]({"action": action, **msg}, session, emit, None)
        if taak is not None:
            await taak

    asyncio.run(scenario())


_ACTIES = [("bericht", "message", {"content": "hoeveel studenten?"}), ("rapport", "generate_report", {})]


@pytest.mark.parametrize(("soort", "actie", "msg"), _ACTIES)
def test_zonder_geavanceerd_krijgt_een_gekozen_model_het_standaardmodel(chatsessie, modellen, soort, actie, msg):
    _actie(actie, msg, chatsessie(EXTRA))

    assert modellen == [(soort, STANDAARD)]


@pytest.mark.parametrize(("soort", "actie", "msg"), _ACTIES)
def test_met_geavanceerd_telt_het_gekozen_model(chatsessie, modellen, soort, actie, msg):
    geavanceerd.zet("anna", True)

    _actie(actie, msg, chatsessie(EXTRA))

    assert modellen == [(soort, EXTRA)]


def test_ook_met_geavanceerd_alleen_binnen_het_aanbod(chatsessie, modellen):
    geavanceerd.zet("anna", True)

    _actie("message", {"content": "hoeveel studenten?"}, chatsessie("azure_ai/duur"))

    assert modellen == [("bericht", STANDAARD)]


def test_een_wissel_geldt_meteen_in_een_open_verbinding(chatsessie, modellen):
    """De server leest de instelling bij elke vraag opnieuw: wie haar uitzet, krijgt bij de volgende vraag het
    standaardmodel, zonder opnieuw te verbinden."""
    session = chatsessie(EXTRA)
    geavanceerd.zet("anna", True)
    _actie("message", {"content": "eerste"}, session)
    geavanceerd.zet("anna", False)
    _actie("message", {"content": "tweede"}, session)

    assert modellen == [("bericht", EXTRA), ("bericht", STANDAARD)]


def test_geavanceerd_in_de_settings_van_de_client_telt_niet(chatsessie, modellen):
    async def zet_instellingen():
        await chat.ACTIES["settings"](
            {"action": "settings", "settings": {"model": EXTRA, "geavanceerd": True}}, session, _stil, None
        )

    session = chatsessie(EXTRA)
    asyncio.run(zet_instellingen())
    session["modelkeuze"] = True  # wat een client ook in de sessie probeert: de server leest haar opnieuw
    _actie("message", {"content": "hoeveel studenten?"}, session)

    assert "geavanceerd" not in session["chat_settings"]
    assert modellen == [("bericht", STANDAARD)]
    assert geavanceerd.lees("anna") is False


def test_zonder_login_telt_het_aanbod_zoals_voorheen(chatsessie, modellen, monkeypatch):
    """Zonder login is er geen eigen account om de keuze aan te koppelen: de browser houdt haar, de server begrenst
    alleen tot het aanbod (#755)."""
    monkeypatch.setattr(chat, "AUTH_ENABLED", False)
    session = chat._new_session(username=None)
    session["chat_settings"] = {"model": EXTRA}

    _actie("message", {"content": "hoeveel studenten?"}, session)

    assert modellen == [("bericht", EXTRA)]


async def _stil(_event):
    pass


# ── Criterium 6: beschermende uitvoer is met en zonder Geavanceerd gelijk (serverkant) ──

# Elke beschermende functie met de plek waar ze in de uitvoer van de chat staat. Een nieuwe beschermende functie komt
# hier bij, met dezelfde naam als in BESCHERMEND van frontend/src/__tests__/beschermingInvariant.test.js
# (docs/kwaliteit-en-veiligheid.md, "Altijd aan").
BESCHERMEND: dict[str, tuple[str, str]] = {
    "antwoordcontrole": ("controle", "Het getal 512.100 staat niet in de opgehaalde data."),
    "intrekking": ("vervangen", "Eerdere versie met een getal dat de controle niet vond."),
    "uitgangspunt": ("content", "**Uitgangspunt:**"),
    "niet meegeteld": ("content", "**Niet meegeteld:**"),
    "bron en definitie": ("content", "**Bron en definitie:**"),
    "ondergrens": ("content", "≥ 1.250"),
    "let op": ("content", "Let op: voorlopige cijfers"),
    "citatie in woorden": ("citaties", "CBS StatLine, mbo-studenten landelijk"),
    "scopekaart": ("clarification", "Hogeschool Utrecht"),
    "afwijking van je vraag": ("afwijkingen", "Je vroeg naar 2025; de laatste cijfers zijn van 2024."),
}

_ANTWOORD = "\n\n".join(
    [
        "**Uitgangspunt:** mbo, landelijk, alle opleidingen.",
        "**Niet meegeteld:** de deelnemers aan een vavo-opleiding.",
        "In 2024 waren er 512.100 mbo-studenten; in kleine groepen ≥ 1.250 (ondergrens).",
        "Let op: voorlopige cijfers van CBS.",
        "**Bron en definitie:** CBS StatLine 85354NED, ingeschreven op 1 oktober.",
    ]
)

# Het bevroren antwoord: wat de agent voor deze vraag op bevroren data uitzendt, met elke beschermende functie.
_BEVROREN = [
    {"type": "message_start"},
    {"type": "tool_start", "name": "get_maat", "label": "Vaste maat ophalen"},
    {"type": "tool_end", "name": "get_maat", "snippet": "import pandas as pd", "exportKey": "cbs:85354NED:nep"},
    {
        "type": "clarification",
        "question": "Welke instelling bedoel je?",
        "options": [{"label": "Hogeschool Utrecht"}, {"label": "Universiteit Utrecht"}],
    },
    {
        "type": "message_end",
        "content": _ANTWOORD,
        "controle": [BESCHERMEND["antwoordcontrole"][1]],
        "vervangen": [BESCHERMEND["intrekking"][1]],
        "citaties": [{"getal": "512.100", "bron": BESCHERMEND["citatie in woorden"][1], "key": "cbs:85354NED:nep"}],
        "afwijkingen": [BESCHERMEND["afwijking van je vraag"][1]],
        "bronnen": ["CBS StatLine 85354NED"],
    },
]


def _gesprek(client: TestClient, token: str) -> list[dict]:
    """Eén vraag over de echte chatverbinding; alle events van de beurt, zonder de melding over een modelsleutel."""
    with client.websocket_connect("/api/chat", subprotocols=["bearer", token]) as ws:
        ws.send_text(json.dumps({"action": "settings", "settings": {"model": EXTRA}}))
        ws.send_text(json.dumps({"action": "message", "content": "Hoeveel mbo-studenten zijn er landelijk?"}))
        events = []
        while not events or events[-1]["type"] != "message_end":
            event = json.loads(ws.receive_text())
            if event["type"] != "system_message":
                events.append(event)
    return events


def test_beschermende_uitvoer_is_met_en_zonder_geavanceerd_gelijk(client, monkeypatch):
    gezien: list[str | None] = []

    async def bevroren(messages, session, emit, stop_event, model=None):
        gezien.append(model)
        for event in _BEVROREN:
            await emit(json.loads(json.dumps(event)))
        return _ANTWOORD

    monkeypatch.setattr(chat, "AUTH_ENABLED", True)
    monkeypatch.setattr(chat, "agent_run", bevroren)
    monkeypatch.setattr(chat, "_berichtlimiter", RateLimiter(max_attempts=100, window_seconds=60))
    monkeypatch.setattr(config, "MODEL", STANDAARD)
    monkeypatch.setattr(config, "_AVAILABLE_MODELS_RAW", f"{STANDAARD},{EXTRA}")

    _zet(client, _token("anna"), {"geavanceerd": False})
    uit = _gesprek(client, _token("anna"))
    _zet(client, _token("anna"), {"geavanceerd": True})
    aan = _gesprek(client, _token("anna"))

    # De instelling deed er wel toe: het model wisselde. De uitvoer niet.
    assert gezien == [STANDAARD, EXTRA]
    assert aan == uit
    eind = uit[-1]
    kaart = next(e for e in uit if e["type"] == "clarification")
    for naam, (veld, tekst) in BESCHERMEND.items():
        bron = kaart if veld == "clarification" else eind
        assert tekst in json.dumps(bron.get(veld if veld != "clarification" else "options"), ensure_ascii=False), naam
