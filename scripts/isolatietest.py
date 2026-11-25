#!/usr/bin/env python
"""
Isolatietest met twee accounts tegen een draaiende app (#1235): lokaal of de testomgeving, nooit productie.

Dezelfde controles als tests/test_account_isolatie.py, nu over HTTP met twee echte tokens:
  1. B krijgt op een gesprek, rapport (werkboek), Word-document en rapportfeedback van A dezelfde 404 als op een
     onbekend id;
  2. met --data-key: A krijgt de CSV van die key, B dezelfde 404 als op een onbekende key;
  3. met --data-key: B bewaart die key in een eigen gesprek en krijgt nog steeds geen CSV, en geen recept in zijn export;
  4. de gesprekken, zoekresultaten, werkboeken, gegeven feedback en de export van B noemen A nergens;
  5. met --verwijder-a: na "verwijder al mijn gegevens" van A staat alles van B er precies zo;
  6. zonder token, met onzin en met een vervalst token, en met --token-a-uit ook met een ingetrokken token: 401 op elk
     eindpunt hierboven;
  7. de instelling "Geavanceerd" (#1269): wat A zet, ziet B niet, en B kan die van A niet zetten (ook niet met de naam
     van A in het verzoek); aan het eind krijgt A zijn eigen stand terug.

Gebruik (tokens alleen via de omgeving, nooit als argument: dan staan ze in de shellgeschiedenis):
    export ISOLATIE_URL=https://onderwijsdata-chat.test.sdp.surf.nl
    export ISOLATIE_TOKEN_A=…  ISOLATIE_TOKEN_B=…        # twee eigen accounts, niet `demo`
    export ISOLATIE_TOKEN_A_UIT=…                         # optioneel: een tweede token van A, dat de test uitlogt
    uv run python scripts/isolatietest.py [--data-key duo:p01hoinges:2] [--verwijder-a]

Alleen localhost, 127.0.0.1 en de testomgeving (TOEGESTANE_HOSTS); elke andere URL, ook playground en productie,
weigert hij vóór het eerste verzoek. Hij maakt alleen eigen testgegevens (gesprekken en rapporten met het merkteken
`isolatietest-<run>`) en ruimt ze aan het eind op. --verwijder-a wist ALLES van account A: alleen op het auditaccount.
Er gaat geen vraag naar het taalmodel: de test kost geen tokenbudget. Exitcode 0: alles in orde; 1: een controle faalt;
2: geweigerd (URL of tokens).
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import quote, urlsplit

TESTOMGEVING = "onderwijsdata-chat.test.sdp.surf.nl"
_LOKAAL = frozenset({"localhost", "127.0.0.1"})
TOEGESTANE_HOSTS = _LOKAAL | {TESTOMGEVING}
# Gedeelde accounts: daar zou de test het werk van anderen zien, en --verwijder-a het wissen.
GEDEELDE_ACCOUNTS = frozenset({"demo", "gast"})

_BEVESTIGD = {"bevestig": "verwijder"}
_GEAVANCEERD = "/api/mijn-gegevens/geavanceerd"


class Geweigerd(Exception):
    """De test start niet: verkeerde omgeving of verkeerde tokens."""


class Antwoord(Protocol):
    @property
    def status_code(self) -> int: ...

    @property
    def content(self) -> bytes: ...

    @property
    def text(self) -> str: ...

    def json(self) -> Any: ...


# (methode, pad, token of None, JSON-lichaam of None) -> antwoord. Zo draait de test ook in pytest, op een TestClient.
Vraag = Callable[[str, str, str | None, object], Antwoord]


def controleer_url(url: str) -> str:
    """De basis-URL, alleen voor lokaal of de testomgeving (die alleen via https); anders Geweigerd."""
    delen = urlsplit(url.strip())
    host = (delen.hostname or "").lower()
    if host not in TOEGESTANE_HOSTS:
        raise Geweigerd(
            f"{host or url!r} is niet lokaal en niet de testomgeving ({TESTOMGEVING}): "
            "deze test draait nooit op productie, playground of een andere omgeving."
        )
    if host not in _LOKAAL and delen.scheme != "https":
        raise Geweigerd(f"de testomgeving alleen via https, niet {delen.scheme or 'zonder schema'}.")
    if delen.scheme not in ("http", "https"):
        raise Geweigerd(f"{url!r} is geen http(s)-URL.")
    return f"{delen.scheme}://{delen.netloc}"


def gebruiker_van(token: str) -> str | None:
    """De gebruikersnaam uit de payload van een token (`<user>|<start>|<exp>`, core/auth.py), zonder de handtekening
    te toetsen: dat doet de server. None als het geen leesbaar token is."""
    payload, sep, _ = token.rpartition(".")
    if not sep:
        return None
    try:
        claims = base64.urlsafe_b64decode(payload + "==").decode()
    except ValueError:
        return None
    naam, sep, _ = claims.partition("|")
    return naam if sep and naam else None


def controleer_tokens(token_a: str, token_b: str) -> tuple[str, str]:
    """De twee accountnamen; Geweigerd bij een onleesbaar token, twee keer hetzelfde account of een gedeeld account."""
    a, b = gebruiker_van(token_a), gebruiker_van(token_b)
    if a is None or b is None:
        raise Geweigerd("ISOLATIE_TOKEN_A en ISOLATIE_TOKEN_B moeten tokens van de app zijn (POST /api/auth/login).")
    if a == b:
        raise Geweigerd("A en B zijn hetzelfde account: de test vraagt twee verschillende accounts.")
    if gedeeld := {a, b} & GEDEELDE_ACCOUNTS:
        raise Geweigerd(f"{', '.join(sorted(gedeeld))} is een gedeeld account: gebruik twee eigen testaccounts.")
    return a, b


def _andere_handtekening(token: str) -> str:
    return token[:-1] + ("0" if token[-1:] != "0" else "1")


@dataclass
class Uitslag:
    geslaagd: list[str] = field(default_factory=list)
    fouten: list[str] = field(default_factory=list)

    def toets(self, ok: bool, wat: str) -> None:
        (self.geslaagd if ok else self.fouten).append(wat)


def _gesprek(merk: str, data_key: str | None) -> dict:
    tools = [{"name": "get_duo_data", "dataKey": data_key, "exportKey": data_key}] if data_key else []
    return {
        "title": f"Isolatietest {merk}",
        "timestamp": 1_700_000_000,
        "messages": [
            {"role": "user", "content": f"Isolatietest {merk}"},
            {"role": "assistant", "content": f"Testantwoord {merk}", "tools": tools},
        ],
    }


def _werkboek(merk: str) -> dict:
    return {"title": f"Isolatietest {merk}", "description": merk, "htmlContent": f"<p>{merk}</p>", "createdAt": ""}


def _feedback(wb_id: str) -> dict:
    return {"workbook_id": wb_id, "report_type": "report", "report_title": "isolatietest", "answers": {"nuttig": "4"}}


def _csv(key: str) -> str:
    return f"/api/data/csv?key={quote(key, safe='')}"


def voer_uit(
    vraag: Vraag,
    token_a: str,
    token_b: str,
    *,
    data_key: str | None = None,
    token_a_uit: str | None = None,
    verwijder_a: bool = False,
    run: str | None = None,
) -> Uitslag:
    """De zes controles met A en B; maakt alleen gegevens met het merkteken van deze run en ruimt die op."""
    run = run or uuid.uuid4().hex[:8]
    merk_a, merk_b = f"isolatietest-{run}-a", f"isolatietest-{run}-b"
    gesprek_b2 = f"{merk_b}-2"
    onbekend = f"isolatietest-{run}-bestaat-niet"
    uitslag = Uitslag()
    naam_a = gebruiker_van(token_a) or ""
    a_gewist = False
    geavanceerd_a: bool | None = None  # de eigen stand van A, om hem aan het eind terug te zetten

    def stel_in(methode: str, pad: str, token: str, body: object) -> None:
        status = vraag(methode, pad, token, body).status_code
        if status != 200:
            raise Geweigerd(f"klaarzetten mislukt: {methode} {pad} gaf {status}")

    try:
        stel_in("PUT", f"/api/conversations/{merk_a}", token_a, _gesprek(merk_a, data_key))
        stel_in("PUT", f"/api/workbooks/{merk_a}", token_a, _werkboek(merk_a))
        stel_in("PUT", f"/api/conversations/{merk_b}", token_b, _gesprek(merk_b, None))
        stel_in("PUT", f"/api/workbooks/{merk_b}", token_b, _werkboek(merk_b))

        # 1 en 2: iets van A is voor B niet te onderscheiden van iets onbekends.
        vergelijk: list[tuple[str, Callable[[str], tuple[str, str, object]]]] = [
            ("gesprek lezen", lambda i: ("GET", f"/api/conversations/{i}", None)),
            ("gesprek hernoemen", lambda i: ("PATCH", f"/api/conversations/{i}", {"title": "van B"})),
            ("rapport lezen", lambda i: ("GET", f"/api/workbooks/{i}", None)),
            ("Word-document", lambda i: ("POST", f"/api/workbooks/{i}/docx", None)),
            ("rapportfeedback", lambda i: ("POST", "/api/feedback", _feedback(i))),
        ]
        for wat, verzoek in vergelijk:
            vreemd, leeg = vraag(*_met(verzoek(merk_a), token_b)), vraag(*_met(verzoek(onbekend), token_b))
            uitslag.toets(
                vreemd.status_code == 404 and vreemd.content == leeg.content,
                f"1/2 {wat}: B krijgt {vreemd.status_code}, gelijk aan een onbekend id: {vreemd.content == leeg.content}",
            )
        if data_key:
            eigen = vraag("GET", _csv(data_key), token_a, None)
            uitslag.toets(eigen.status_code == 200, f"2 CSV: A krijgt de eigen key ({eigen.status_code})")
            _csv_van_b(vraag, token_b, data_key, uitslag, "2 CSV")
            # 3: de key van A in een eigen gesprek van B.
            stel_in("PUT", f"/api/conversations/{gesprek_b2}", token_b, _gesprek(merk_b, data_key))
            _csv_van_b(vraag, token_b, data_key, uitslag, "3 key van A in een gesprek van B, CSV")
            recepten = vraag("GET", "/api/mijn-gegevens/export", token_b, None).json().get("data_recipes", [])
            uitslag.toets(
                all(r.get("data_key") != data_key for r in recepten if isinstance(r, dict)),
                "3 key van A in een gesprek van B: geen recept in de export van B",
            )

        # 4: niets van A in wat B ziet.
        # De naam van A als JSON-tekst: "audit" mag niet aanslaan op een B die "audit-2" heet.
        sporen = [merk_a, json.dumps(naam_a)] if naam_a else [merk_a]
        for pad in (
            "/api/conversations",
            f"/api/conversations?q={merk_a}",
            "/api/workbooks",
            "/api/feedback/given",
            "/api/mijn-gegevens/export",
        ):
            antwoord = vraag("GET", pad, token_b, None)
            gevonden = [s for s in sporen if s in antwoord.text]
            uitslag.toets(
                antwoord.status_code == 200 and not gevonden,
                f"4 {pad.split('?')[0]}: {antwoord.status_code}, sporen van A: {len(gevonden)}",
            )
        export_b = vraag("GET", "/api/mijn-gegevens/export", token_b, None).text
        uitslag.toets(merk_b in export_b, "4 de export van B bevat wel B's eigen werk")

        # 7: "Geavanceerd" van A is voor B niet te lezen of te zetten.
        lees_a, lees_b = vraag("GET", _GEAVANCEERD, token_a, None), vraag("GET", _GEAVANCEERD, token_b, None)
        if lees_a.status_code == 200 and lees_b.status_code == 200:
            geavanceerd_a, eigen_b = lees_a.json().get("geavanceerd"), lees_b.json().get("geavanceerd")
            anders = not eigen_b
            stel_in("PUT", _GEAVANCEERD, token_a, {"geavanceerd": anders})
            na = vraag("GET", _GEAVANCEERD, token_b, None).json()
            uitslag.toets(na == {"geavanceerd": eigen_b}, f"7 Geavanceerd: A zet {anders}, B ziet zijn eigen {na}")
            overname = vraag("PUT", _GEAVANCEERD, token_b, {"geavanceerd": eigen_b, "username": naam_a})
            uitslag.toets(
                overname.status_code == 422, f"7 Geavanceerd: B met de naam van A krijgt {overname.status_code}"
            )
            van_a = vraag("GET", _GEAVANCEERD, token_a, None).json()
            uitslag.toets(van_a == {"geavanceerd": anders}, f"7 Geavanceerd: die van A is ongewijzigd ({van_a})")
        else:
            uitslag.toets(False, f"7 Geavanceerd: GET gaf {lees_a.status_code} voor A en {lees_b.status_code} voor B")

        # 6: zonder geldig token 401 op elk eindpunt.
        eindpunten: list[tuple[str, str, object]] = [
            ("GET", "/api/conversations", None),
            ("GET", f"/api/conversations/{merk_a}", None),
            ("PUT", f"/api/conversations/{merk_a}", _gesprek("overgenomen", None)),
            ("PATCH", f"/api/conversations/{merk_a}", {"title": "overgenomen"}),
            ("DELETE", f"/api/conversations/{merk_a}", None),
            ("GET", "/api/workbooks", None),
            ("GET", f"/api/workbooks/{merk_a}", None),
            ("PUT", f"/api/workbooks/{merk_a}", _werkboek("overgenomen")),
            ("DELETE", f"/api/workbooks/{merk_a}", None),
            ("POST", f"/api/workbooks/{merk_a}/docx", None),
            ("GET", _csv(data_key or "duo:p01hoinges:0"), None),
            ("POST", "/api/feedback", _feedback(merk_a)),
            ("GET", "/api/feedback/given", None),
            ("GET", "/api/mijn-gegevens/export", None),
            ("DELETE", "/api/mijn-gegevens", _BEVESTIGD),
            ("GET", _GEAVANCEERD, None),
            ("PUT", _GEAVANCEERD, {"geavanceerd": True}),
        ]
        ongeldig: dict[str, str | None] = {
            "zonder token": None,
            "onzin": "onzin",
            "vervalste handtekening": _andere_handtekening(token_a),
        }
        if token_a_uit:
            uitgelogd = vraag("POST", "/api/auth/logout", token_a_uit, None).status_code
            uitslag.toets(uitgelogd == 204, f"6 tweede token van A uitgelogd ({uitgelogd})")
            ongeldig["ingetrokken"] = token_a_uit
        for soort, token in ongeldig.items():
            mis = [f"{m} {p}: {s}" for m, p, b in eindpunten if (s := vraag(m, p, token, b).status_code) != 401]
            uitslag.toets(not mis, f"6 {soort}: 401 op {len(eindpunten) - len(mis)}/{len(eindpunten)} {mis}")
        nog = vraag("GET", f"/api/conversations/{merk_a}", token_a, None)
        uitslag.toets(
            nog.status_code == 200 and nog.json().get("title") == f"Isolatietest {merk_a}",
            "6 het gesprek van A is na de geweigerde verzoeken ongewijzigd",
        )

        # 5: A wist alles; B houdt alles.
        if verwijder_a:
            voor = _momentopname(vraag, token_b, merk_b)
            gewist = vraag("DELETE", "/api/mijn-gegevens", token_a, _BEVESTIGD)
            a_gewist = gewist.status_code == 200
            uitslag.toets(a_gewist, f"5 A verwijdert al zijn gegevens ({gewist.status_code})")
            na = vraag("GET", "/api/conversations", token_a, None).status_code
            uitslag.toets(na == 401, f"5 daarna geldt het token van A niet meer ({na})")
            uitslag.toets(_momentopname(vraag, token_b, merk_b) == voor, "5 alles van B staat er precies zo")
    finally:
        for methode, pad, token in (
            ("DELETE", f"/api/conversations/{merk_b}", token_b),
            ("DELETE", f"/api/conversations/{gesprek_b2}", token_b),
            ("DELETE", f"/api/workbooks/{merk_b}", token_b),
            ("DELETE", f"/api/conversations/{merk_a}", token_a),
            ("DELETE", f"/api/workbooks/{merk_a}", token_a),
        ):
            if not (a_gewist and token == token_a):
                vraag(methode, pad, token, None)
        if geavanceerd_a is not None and not a_gewist:
            vraag("PUT", _GEAVANCEERD, token_a, {"geavanceerd": geavanceerd_a})
    return uitslag


def _met(verzoek: tuple[str, str, object], token: str) -> tuple[str, str, str, object]:
    methode, pad, body = verzoek
    return methode, pad, token, body


def _csv_van_b(vraag: Vraag, token_b: str, data_key: str, uitslag: Uitslag, wat: str) -> None:
    vreemd = vraag("GET", _csv(data_key), token_b, None)
    leeg = vraag("GET", _csv("duo:isolatietest-bestaat-niet:0"), token_b, None)
    uitslag.toets(
        vreemd.status_code == 404 and vreemd.content == leeg.content,
        f"{wat}: B krijgt {vreemd.status_code}, gelijk aan een onbekende key: {vreemd.content == leeg.content}",
    )


def _momentopname(vraag: Vraag, token: str, gesprek: str) -> dict:
    """Wat B ziet, zonder een werkboek te openen (openen verzet de bewaartermijn) en zonder het exportmoment."""
    export = vraag("GET", "/api/mijn-gegevens/export", token, None).json()
    export.pop("exported_at", None)
    return {
        "gesprekken": vraag("GET", "/api/conversations", token, None).json(),
        "gesprek": vraag("GET", f"/api/conversations/{gesprek}", token, None).json(),
        "werkboeken": vraag("GET", "/api/workbooks", token, None).json(),
        "feedback": vraag("GET", "/api/feedback/given", token, None).json(),
        "export": export,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-key", help="een data-key uit een gesprek van A (controle 2 en 3)")
    parser.add_argument("--verwijder-a", action="store_true", help="controle 5: wist ALLES van account A")
    args = parser.parse_args(argv)
    try:
        basis = controleer_url(os.environ.get("ISOLATIE_URL", ""))
        token_a, token_b = os.environ.get("ISOLATIE_TOKEN_A", ""), os.environ.get("ISOLATIE_TOKEN_B", "")
        naam_a, naam_b = controleer_tokens(token_a, token_b)
    except Geweigerd as fout:
        print(f"Geweigerd: {fout}", file=sys.stderr)
        return 2

    import httpx

    with httpx.Client(base_url=basis, timeout=60) as client:

        def vraag(methode: str, pad: str, token: str | None, body: object) -> Antwoord:
            kop = {"Authorization": f"Bearer {token}"} if token else {}
            return client.request(methode, pad, headers=kop, json=body)

        print(f"Isolatietest op {basis}: A={naam_a}, B={naam_b}")
        try:
            uitslag = voer_uit(
                vraag,
                token_a,
                token_b,
                data_key=args.data_key,
                token_a_uit=os.environ.get("ISOLATIE_TOKEN_A_UIT") or None,
                verwijder_a=args.verwijder_a,
            )
        except Geweigerd as fout:
            print(f"Geweigerd: {fout}", file=sys.stderr)
            return 2
    for wat in uitslag.geslaagd:
        print(f"OK    {wat}")
    for wat in uitslag.fouten:
        print(f"FOUT  {wat}")
    print(f"{len(uitslag.geslaagd)} in orde, {len(uitslag.fouten)} fout")
    return 1 if uitslag.fouten else 0


if __name__ == "__main__":
    sys.exit(main())
