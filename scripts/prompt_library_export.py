"""Maakt het importbestand voor de Prompt Library uit data/prompt-library/vragen.json (#1047, B).

De library importeert JSON of CSV met vaste kolommen (ADR-018 in de library, `app/importing.py`) en maakt van elke rij
een concept van degene die importeert; een redacteur keurt het daarna goed. De prompttekst van elke rij is een vraag
uit `tests/e2e/evaluations.json`, de geteste vragen met bekende uitkomsten. De kolom `bron` heeft de deep link
(`/chat#vraag=…`, docs/api.md), zodat een lezer de vraag in één klik in EDUdata opent.

    uv run python scripts/prompt_library_export.py --basis-url https://<omgeving> > vragen-aan-onderwijsdata.json

`--basis-url` is verplicht: de verzameling hoort naar één omgeving te wijzen, en welke dat is (productie is nog niet
live) is een besluit van de beheerder, niet van dit script. De kolom `getest_in` blijft leeg: de library kent "Getest in"
als gesloten lijst van AI-producten (ADR-008), en EDUdata staat daar niet op. De kolom `licentie` is CC BY 4.0: de
vragen en hun toelichting vallen onder die licentie (besluit van 19-11-2026). De library kent een gesloten lijst
licenties; de waarde moet er exact in staan, anders weigert de import het hele bestand.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import quote, urlsplit

ROOT = Path(__file__).resolve().parent.parent
VRAGEN = ROOT / "data" / "prompt-library" / "vragen.json"
EVALUATIES = ROOT / "tests" / "e2e" / "evaluations.json"

# De grens van de deep link (frontend/src/voorgevuldeVraag.js), en van de kolom `bron` in de library.
MAX_VRAAG = 500
MAX_BRON = 500

# De licentie van de vragen en hun toelichting. Exact een waarde uit de gesloten lijst van de library
# (`COPYRIGHT` in app/suggestions.py daar).
LICENTIE = "CC BY 4.0"


def evaluatievragen() -> dict[str, str]:
    """label → vraagtekst, uit de evaluatieset."""
    data = json.loads(EVALUATIES.read_text(encoding="utf-8"))
    return {e["label"]: e["message"] for e in data["evaluations"]}


def deep_link(basis_url: str, vraag: str) -> str:
    """`https://<omgeving>/chat#vraag=<vraag>`, de stabiele interface uit docs/api.md."""
    deel = urlsplit(basis_url)
    if deel.scheme != "https" or not deel.netloc or deel.path not in ("", "/") or deel.query or deel.fragment:
        raise ValueError(f"--basis-url moet er zo uitzien: https://<omgeving> (kreeg {basis_url!r})")
    return f"{deel.scheme}://{deel.netloc}/chat#vraag={quote(vraag, safe='')}"


def rijen(basis_url: str) -> list[dict[str, str]]:
    """De rijen van het importbestand, in de kolomnamen van de library."""
    vragen = evaluatievragen()
    uit: list[dict[str, str]] = []
    for item in json.loads(VRAGEN.read_text(encoding="utf-8"))["vragen"]:
        label = item["eval"]
        if label not in vragen:
            raise ValueError(f"{label!r} staat niet in tests/e2e/evaluations.json")
        vraag = vragen[label]
        if len(vraag) > MAX_VRAAG or "\n" in vraag:
            raise ValueError(f"{label!r}: een deep link neemt één regel van hoogstens {MAX_VRAAG} tekens")
        bron = f"EDUdata, een geteste vraag uit de evaluatieset. Open in EDUdata: {deep_link(basis_url, vraag)}"
        if len(bron) > MAX_BRON:
            raise ValueError(f"{label!r}: de bron is {len(bron)} tekens, de library neemt er {MAX_BRON}")
        uit.append(
            {
                "titel": item["titel"],
                "samenvatting": item["samenvatting"],
                "prompttekst": vraag,
                "taal": "nl",
                "tips": item["tips"],
                "waarom_dit_werkt": item["waarom_dit_werkt"],
                "bron": bron,
                "licentie": LICENTIE,
                "labels": f"{item['labels']}; tag:onderwijsdata; tag:EDUdata",
            }
        )
    return uit


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--basis-url", required=True, help="https://<omgeving> van EDUdata, zonder pad")
    args = ap.parse_args(argv)
    try:
        uit = rijen(args.basis_url)
    except ValueError as exc:
        print(f"fout: {exc}", file=sys.stderr)
        return 1
    json.dump(uit, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
