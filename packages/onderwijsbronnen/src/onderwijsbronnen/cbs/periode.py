"""Loopt de `periode` van een CBS-record achter op de tabel zelf? (#1070)

`periode` is de tekst die CBS bij de tabel zet (TableInfos `Period`, in elke tabel anders geschreven: "2006/'07-2023/'24",
"2013 - 2025", "2015/'16-2025/26"). `_periode_waarden` komt uit de Perioden-dimensie en is de eerste en de laatste
periode die de tabel heeft. Vergelijken doen we het eindjaar: de schrijfwijzen verschillen, het jaar niet.
"""

import re

# Een jaar, met een eventueel studiejaar erachter ("2023/'24", "2025/26", "2022/'2023"): het studiejaar telt als het
# jaar waarin het begint.
_JAAR = re.compile(r"(?<!\d)(\d{4})(?:\s*/\s*['’]?\d{2,4})?(?!\d)")


# "2021 tot 2026" is het blok 2021 t/m 2025 (de vijfjaarsblokken van CBS); "tot en met" sluit het jaar wel in.
_TOT = re.compile(r"\btot\s+(?!en\s+met\b)\d{4}\s*$")


def eindjaar(tekst: str) -> int | None:
    """Het laatste jaar dat de tekst noemt; None als er geen jaar in staat."""
    jaren = _JAAR.findall(tekst or "")
    if not jaren:
        return None
    return int(jaren[-1]) - (1 if _TOT.search(tekst) else 0)


def loopt_achter(record: dict) -> bool:
    """Eindigt de `periode` van het record vóór de laatste periode van de tabel (`_periode_waarden`)?

    Zonder waarden of zonder jaar in de tekst valt er niets te vergelijken: dan is het antwoord nee, want het record
    is niet aantoonbaar achter.
    """
    waarden = record.get("_periode_waarden") or []
    tekst_jaar = eindjaar(record.get("periode") or "")
    tabel_jaar = eindjaar(waarden[-1]) if waarden else None
    return tekst_jaar is not None and tabel_jaar is not None and tekst_jaar < tabel_jaar


def beginjaar(tekst: str) -> int | None:
    """Het eerste jaar dat de tekst noemt; None als er geen jaar in staat."""
    jaren = _JAAR.findall(tekst or "")
    return int(jaren[0]) if jaren else None


def bij_tabel(tekst: str, labels: list[str]) -> str:
    """De periodetekst van CBS, of het bereik van de tabel zelf als CBS de tekst niet bijhoudt (#1070).

    `labels` zijn alle perioden van de tabel in volgorde. CBS zet bij een nieuwe periode soms alleen de tabel bij:
    85566NED zegt "t/m 2023/'24 naar 2024/'25" en heeft ook 2024/'25 naar 2025/'26. En de tekst begint soms later dan
    de tabel (85379NED zegt 2021/'22, de tabel begint in 2011/'12). Dan volgt de tekst de tabel. Een tabel met twee
    perioden noemt beide, want "2019-2025" suggereert de jaren ertussen.
    """
    if not labels:
        return tekst
    eerste, laatste = labels[0], labels[-1]
    begint_anders = beginjaar(tekst) is not None and beginjaar(eerste) not in (None, beginjaar(tekst))
    if tekst and not (begint_anders or loopt_achter({"periode": tekst, "_periode_waarden": [eerste, laatste]})):
        return tekst
    if len(labels) == 1:
        return eerste
    if len(labels) == 2:
        return f"{eerste} en {laatste}"
    return f"{eerste} t/m {laatste}" if "naar" in eerste + laatste else f"{eerste}-{laatste}"
