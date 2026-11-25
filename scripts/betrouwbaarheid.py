#!/usr/bin/env python
"""
De betrouwbaarheid per release op de docs-site (#1246): de uitslag van een `eval:bronwaarheid`-run naar
`docs/betrouwbaarheid.md`.

Gebruik:
    uv run python scripts/betrouwbaarheid.py \\
        --slagingspercentage eval_results/slagingspercentage-<datum>.json --versie X.Y.Z --commit <volledige commit>

Het script leest het slagingspercentage per model en vraag (`tests/e2e/matrix.js`) en het kritieke rapport
(`tests/e2e/kritiek.js`; standaard `kritiek-<datum>.json` naast het slagingspercentage). Het schrijft per release één
rij in het overzicht (datum, versie, commit, modellen, herhalingen, slagingspercentage per model, de kritieke set en de
kritieke weigeringen) en een sectie met per vraag geslaagd of niet, met een link naar de vraag en de ijkwaarde op de
publieke spiegel, op de commit van de release. Oude releases blijven staan; dezelfde release opnieuw vervangt haar rij
en sectie (idempotent). Een slechte score wordt net zo gepubliceerd als een goede.

Geen netwerk en geen model: versie en commit komen van de opdrachtregel (`curl <test-url>/version` tijdens de run),
de vragen en ijkwaarden uit `tests/e2e/`. De stap in de release staat in `docs/promoten.md`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGINA = ROOT / "docs" / "betrouwbaarheid.md"
EVALS = ROOT / "tests" / "e2e" / "evaluations.json"
IJKWAARDEN = ROOT / "tests" / "e2e" / "ijkwaarden.json"
# De publieke spiegel van deze repo (core/pakketherkomst.py): de docs-site staat daar ook.
SPIEGEL_URL = "https://github.com/cedanl/onderwijsdata-chat"

OVERZICHT_BEGIN = "<!-- betrouwbaarheid:overzicht -->"
OVERZICHT_EINDE = "<!-- /betrouwbaarheid:overzicht -->"
RELEASES_BEGIN = "<!-- betrouwbaarheid:releases -->"
RELEASES_EINDE = "<!-- /betrouwbaarheid:releases -->"
KOP = (
    "| Datum | Versie | Commit | Modellen | Herhalingen | Geslaagd per model | Kritieke set | Kritieke weigeringen |\n"
    "|---|---|---|---|---|---|---|---|"
)

RELEASE_RE = re.compile(r"^\d+\.\d+\.\d+$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
KORT = 8


@dataclass(frozen=True)
class Release:
    versie: str
    commit: str
    datum: str
    herhalingen: int
    slaging: dict  # model → { vragen, beurten, geslaagd, percentage } (matrix.js)
    kritiek: dict  # model → { gehaald, totaal, rood, vragen } (kritiek.js)

    @property
    def anker(self) -> str:
        return "release-" + self.versie.replace(".", "-")

    @property
    def modellen(self) -> list[str]:
        return list(self.slaging)


def _lees(pad: Path) -> dict:
    try:
        data = json.loads(pad.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as fout:
        raise SystemExit(f"{pad}: niet te lezen ({fout})") from fout
    if not isinstance(data, dict) or not isinstance(data.get("modellen"), dict) or not data["modellen"]:
        raise SystemExit(f"{pad}: geen verslag van een eval-run (modellen ontbreekt of is leeg)")
    return data


def kritiek_naast(slagingspercentage: Path) -> Path:
    """Het kritieke rapport van dezelfde run: `kritiek-<datum>.json` in dezelfde map (runlog.js)."""
    return slagingspercentage.with_name(slagingspercentage.name.replace("slagingspercentage-", "kritiek-", 1))


def _datum(verslag: dict, pad: Path) -> str:
    datum = str(verslag.get("gemeten_op") or "")
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", datum):
        raise SystemExit(f"{pad}: gemeten_op ontbreekt of is geen datum")
    return datum


def lees_release(slagingspercentage: Path, kritiek: Path | None, *, versie: str, commit: str) -> Release:
    if not RELEASE_RE.match(versie):
        raise SystemExit(f"versie {versie!r}: verwacht X.Y.Z, zonder v (docs/promoten.md)")
    if not COMMIT_RE.match(commit):
        raise SystemExit(f"commit {commit!r}: verwacht de volledige commit (40 tekens), zoals /version hem noemt")
    slaging = _lees(slagingspercentage)
    krit = _lees(kritiek or kritiek_naast(slagingspercentage))
    return Release(
        versie=versie,
        commit=commit,
        datum=_datum(slaging, slagingspercentage),
        herhalingen=int(slaging.get("herhalingen") or 1),
        slaging=slaging["modellen"],
        kritiek={m: v for m, v in krit["modellen"].items() if m in slaging["modellen"]},
    )


def _kort(model: str) -> str:
    return model.rsplit("/", 1)[-1]


def _nl(getal: int | float) -> str:
    """Een getal in Nederlandse notatie: 7.408."""
    return f"{getal:,}".replace(",", ".") if isinstance(getal, int) else str(getal).replace(".", ",")


def _evals() -> list[dict]:
    return json.loads(EVALS.read_text(encoding="utf-8"))["evaluations"]


def _regelnummers(pad: Path, sleutels: list[str], vorm: str) -> dict[str, int]:
    """Het regelnummer van elke sleutel in een JSON-bestand, voor een link `#L<n>` op de spiegel."""
    regels = pad.read_text(encoding="utf-8").splitlines()
    uit: dict[str, int] = {}
    for sleutel in sleutels:
        zoek = vorm.format(sleutel=sleutel)
        uit[sleutel] = next((i for i, r in enumerate(regels, 1) if zoek in r), 1)
    return uit


def _weigeringen(evals: list[dict]) -> set[str]:
    return {ev["label"] for ev in evals if ev.get("expected", {}).get("must_refuse")}


def _rij(r: Release, evals: list[dict]) -> str:
    weigeringen = _weigeringen(evals)
    geslaagd, kritiek, geweigerd = [], [], []
    for model in r.modellen:
        s = r.slaging[model]
        geslaagd.append(f"{_kort(model)}: {s.get('percentage')}% ({s.get('geslaagd')} van {s.get('beurten')})")
        k = r.kritiek.get(model)
        if not k:
            kritiek.append(f"{_kort(model)}: geen rapport")
            geweigerd.append(f"{_kort(model)}: geen rapport")
            continue
        kritiek.append(f"{_kort(model)}: {k.get('gehaald')} van {k.get('totaal')}")
        vragen = {label: v for label, v in (k.get("vragen") or {}).items() if label in weigeringen}
        rood = [label for label, v in vragen.items() if not v.get("gehaald")]
        tekst = f"{_kort(model)}: {len(vragen) - len(rood)} van {len(vragen)}"
        geweigerd.append(tekst + (f" (rood: {', '.join(rood)})" if rood else ""))
    cellen = [
        r.datum,
        f"[{r.versie}](#{r.anker})",
        f"[`{r.commit[:KORT]}`]({SPIEGEL_URL}/commit/{r.commit})",
        ", ".join(_kort(m) for m in r.modellen),
        str(r.herhalingen),
        "<br>".join(geslaagd),
        "<br>".join(kritiek),
        "<br>".join(geweigerd),
    ]
    return "| " + " | ".join(cellen) + " |"


def _uitslag(cel: dict | None) -> str:
    if not cel or not cel.get("beurten"):
        return "niet gedraaid"
    oordeel = "geslaagd" if cel.get("geslaagd") == cel.get("beurten") else "niet geslaagd"
    return f"{oordeel} ({cel.get('geslaagd')} van {cel.get('beurten')})"


def _referenties(ev: dict, ijk: dict, ijkregels: dict[str, int], blob: str) -> str:
    dp = ev.get("expected", {}).get("data_points") or {}
    if verwijzingen := dp.get("ijkwaarden"):
        delen = []
        for ijk_id in verwijzingen.values():
            w = ijk.get(ijk_id, {})
            tekst = f"{_nl(w.get('waarde', '?'))} ({w.get('schooljaar', '?')})"
            delen.append(f"[{tekst}]({blob}/tests/e2e/ijkwaarden.json#L{ijkregels.get(ijk_id, 1)})")
        return ", ".join(delen)
    if waarden := dp.get("reference_values"):
        return ", ".join(f"{_nl(v)} ({k})" for k, v in waarden.items())
    return "–"


def _sectie(r: Release, evals: list[dict]) -> str:
    blob = f"{SPIEGEL_URL}/blob/{r.commit}"
    labels = list(dict.fromkeys(label for model in r.modellen for label in r.slaging[model].get("vragen", {})))
    per_label = {ev["label"]: ev for ev in evals}
    evalregels = _regelnummers(EVALS, labels, '"label": "{sleutel}"')
    ijk = json.loads(IJKWAARDEN.read_text(encoding="utf-8"))["waarden"]
    ijk_ids = [
        i
        for label in labels
        for i in (
            (per_label.get(label, {}).get("expected", {}).get("data_points") or {}).get("ijkwaarden") or {}
        ).values()
    ]
    ijkregels = _regelnummers(IJKWAARDEN, ijk_ids, '"{sleutel}": {{')
    regels = [
        f"<!-- release {r.versie} -->",
        "",
        f"### {r.versie} ({r.datum}) {{#{r.anker}}}",
        "",
        f"Commit [`{r.commit[:KORT]}`]({SPIEGEL_URL}/commit/{r.commit}), {r.herhalingen} herhalingen per vraag en model, "
        f"op de testomgeving. Modellen: {', '.join(f'`{m}`' for m in r.modellen)}. Geslaagd is een vraag als elke "
        "herhaling slaagt.",
        "",
        "| Vraag | Kritiek | " + " | ".join(_kort(m) for m in r.modellen) + " | Ijkwaarde |",
        "|---|---|" + "---|" * len(r.modellen) + "---|",
    ]
    for label in labels:
        ev = per_label.get(label, {})
        ex = ev.get("expected", {})
        kritiek = ("ja, weigering" if ex.get("must_refuse") else "ja") if ex.get("kritiek") else "nee"
        uitslagen = [_uitslag(r.slaging[m].get("vragen", {}).get(label)) for m in r.modellen]
        vraag = f"[{label}]({blob}/tests/e2e/evaluations.json#L{evalregels[label]})"
        referenties = _referenties(ev, ijk, ijkregels, blob)
        regels.append("| " + " | ".join([vraag, kritiek, *uitslagen, referenties]) + " |")
    regels += ["", f"<!-- /release {r.versie} -->"]
    return "\n".join(regels)


def _blok(tekst: str, begin: str, einde: str) -> tuple[str, str, str]:
    if begin not in tekst or einde not in tekst:
        raise SystemExit(f"de pagina mist de markering {begin} of {einde}")
    voor, rest = tekst.split(begin, 1)
    midden, na = rest.split(einde, 1)
    return voor, midden, na


def _versie_van_rij(rij: str) -> str | None:
    m = re.match(r"^\|[^|]*\|\s*\[(\d+\.\d+\.\d+)\]", rij)
    return m.group(1) if m else None


def werk_bij(tekst: str, r: Release, evals: list[dict] | None = None) -> str:
    """De pagina met de rij en de sectie van deze release; een release die er al staat, wordt vervangen."""
    evals = _evals() if evals is None else evals
    voor, midden, na = _blok(tekst, OVERZICHT_BEGIN, OVERZICHT_EINDE)
    rijen = [regel for regel in midden.splitlines() if _versie_van_rij(regel)]
    nieuw = _rij(r, evals)
    bestaand = [i for i, regel in enumerate(rijen) if _versie_van_rij(regel) == r.versie]
    if bestaand:
        rijen[bestaand[0]] = nieuw
    else:
        rijen.insert(0, nieuw)
    # Met witregels om de markeringen: anders leest Markdown de tabel als deel van het HTML-commentaar.
    tekst = f"{voor}{OVERZICHT_BEGIN}\n\n{KOP}\n" + "\n".join(rijen) + f"\n\n{OVERZICHT_EINDE}{na}"

    voor, midden, na = _blok(tekst, RELEASES_BEGIN, RELEASES_EINDE)
    sectie = re.compile(r"<!-- release (?P<versie>\S+) -->\n.*?<!-- /release (?P=versie) -->", re.DOTALL)
    inhoud = {m["versie"]: m[0] for m in sectie.finditer(midden)}
    secties = list(inhoud)
    volgorde = secties if r.versie in inhoud else [r.versie, *secties]
    inhoud[r.versie] = _sectie(r, evals)
    return f"{voor}{RELEASES_BEGIN}\n\n" + "\n\n".join(inhoud[v] for v in volgorde) + f"\n\n{RELEASES_EINDE}{na}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[1], formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--slagingspercentage", type=Path, required=True, help="eval_results/slagingspercentage-<datum>.json"
    )
    parser.add_argument("--kritiek", type=Path, help="standaard kritiek-<datum>.json naast het slagingspercentage")
    parser.add_argument("--versie", required=True, help="de release, X.Y.Z")
    parser.add_argument("--commit", required=True, help="de volledige commit van de gemeten build (/version)")
    parser.add_argument("--pagina", type=Path, default=PAGINA)
    args = parser.parse_args(argv)
    release = lees_release(args.slagingspercentage, args.kritiek, versie=args.versie, commit=args.commit)
    args.pagina.write_text(werk_bij(args.pagina.read_text(encoding="utf-8"), release), encoding="utf-8")
    print(f"{args.pagina}: release {release.versie} ({release.datum}) bijgewerkt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
