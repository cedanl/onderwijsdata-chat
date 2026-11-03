"""
Fix #2 — Maak het DUO periode-veld informatief met concrete jaarranges.

Gebruik:
  uv run python catalogus/update_duo_periode.py

Werking:
  - Leest src/riodata/data/duo_resources.json
  - Voor elke entry: haalt de eerste CSV-resource op (eerste 4000 bytes + laatste 3000 bytes)
  - Detecteert de jaar-kolom (JAAR, STUDIEJAAR, SCHOOLJAAR, etc.)
  - Bepaalt min- en maxjaar uit de data
  - Formatteert de periode:
      • JAAR / PEILJAAR   → "2010-2024"
      • STUDIEJAAR / SCHOOLJAAR / DIPLOMAJAAR → "2010/'11-2023/'24"
  - Schrijft duo_resources.json terug
"""
from __future__ import annotations

import csv
import io
import json
import re
import sys
import time
from pathlib import Path

import httpx

# ---------------------------------------------------------------------------
# Constanten
# ---------------------------------------------------------------------------

JAAR_KOLOMNAMEN = frozenset({
    "JAAR", "PEILJAAR", "STUDIEJAAR", "SCHOOLJAAR", "DIPLOMAJAAR",
    "SCHOOLJAAR_BEGINNEN", "SCHOOLJAAR_INSTROOM",
})

SCHOOLJAAR_KOLOMNAMEN = frozenset({
    "STUDIEJAAR", "SCHOOLJAAR", "DIPLOMAJAAR",
})

JAAR_RE = re.compile(r"\b(19\d{2}|20[0-2]\d)\b")


# ---------------------------------------------------------------------------
# Jaar-detectie helpers
# ---------------------------------------------------------------------------

def _vind_jaar_kolom_index(header: list[str]) -> tuple[int | None, str | None]:
    """Geef (index, kolomnaam) van de jaar-kolom, of (None, None)."""
    # Exacte match eerst
    for i, col in enumerate(header):
        cu = col.upper().strip()
        if cu in JAAR_KOLOMNAMEN:
            return i, col.strip()
    # Partial match: bevat JAAR maar geen AANTAL
    for i, col in enumerate(header):
        cu = col.upper().strip()
        if "JAAR" in cu and "AANTAL" not in cu and "PERC" not in cu:
            return i, col.strip()
    return None, None


def _extraheer_jaar_uit_cel(waarde: str) -> int | None:
    """Extraheer het eerste 4-cijferige jaar uit een celwaarde (b.v. '2023' of '2023/'24')."""
    m = re.match(r"^[\"']?(\d{4})", waarde.strip())
    if m:
        jaar = int(m.group(1))
        if 1990 <= jaar <= 2030:
            return jaar
    return None


def _scan_jaren_in_tekst(tekst: str) -> list[int]:
    """Zoek alle 4-cijferige jaren (1990-2030) in een tekst."""
    return [int(m) for m in JAAR_RE.findall(tekst) if 1990 <= int(m) <= 2030]


def _parse_jaar_range_uit_csv_fragment(
    start_tekst: str,
    eind_tekst: str,
) -> tuple[int | None, int | None]:
    """Bepaal min- en maxjaar uit een begin- en eind-fragment van een CSV."""
    # Parse header uit begin-fragment
    lines = [l for l in start_tekst.splitlines() if l.strip()]
    if not lines:
        return None, None

    # Detecteer separator
    header_lijn = lines[0]
    sep = "," if "," in header_lijn else (";" if ";" in header_lijn else "\t")

    try:
        reader = csv.reader(io.StringIO(header_lijn), delimiter=sep)
        header = [c.strip().strip('"') for c in next(reader)]
    except StopIteration:
        return None, None

    jaar_idx, _ = _vind_jaar_kolom_index(header)

    if jaar_idx is None:
        # Fallback: scan alle getallen in de datarijen
        datarijen = "\n".join(lines[1:10])
        jaren = _scan_jaren_in_tekst(datarijen)
        start_jaar = min(jaren) if jaren else None

        eind_jaren = _scan_jaren_in_tekst(eind_tekst)
        eind_jaar = max(eind_jaren) if eind_jaren else None
        return start_jaar, eind_jaar

    # Haal startjaar uit eerste datarijen
    start_jaar = None
    for lijn in lines[1:]:
        try:
            rij = next(csv.reader(io.StringIO(lijn), delimiter=sep))
            if len(rij) > jaar_idx:
                waarde = rij[jaar_idx].strip().strip('"')
                j = _extraheer_jaar_uit_cel(waarde)
                if j:
                    start_jaar = j
                    break
        except StopIteration:
            pass

    # Haal eindjaar uit laatste regels van het eind-fragment
    eind_jaar = None
    eind_lines = [l for l in reversed(eind_tekst.splitlines()) if l.strip()]
    for lijn in eind_lines[:20]:
        try:
            rij = next(csv.reader(io.StringIO(lijn), delimiter=sep))
            if len(rij) > jaar_idx:
                waarde = rij[jaar_idx].strip().strip('"')
                j = _extraheer_jaar_uit_cel(waarde)
                if j:
                    eind_jaar = j
                    break
        except StopIteration:
            pass

    # Fallback voor eindjaar als kolom-indexering mislukt
    if eind_jaar is None:
        jaren = _scan_jaren_in_tekst(eind_tekst)
        eind_jaar = max(jaren) if jaren else None

    return start_jaar, eind_jaar


def _formatteer_periode(
    start_jaar: int | None,
    eind_jaar: int | None,
    kolom_naam: str | None,
) -> str | None:
    """Formatteer een periodestring.

    Returns:
        '2010-2024'        voor JAAR/PEILJAAR
        "2010/'11-2023/'24" voor STUDIEJAAR/SCHOOLJAAR/DIPLOMAJAAR
        None als geen informatie beschikbaar
    """
    if start_jaar is None and eind_jaar is None:
        return None

    s = start_jaar or eind_jaar
    e = eind_jaar or start_jaar

    # Zorg dat start <= eind
    if s > e:
        s, e = e, s

    kn = (kolom_naam or "").upper()
    is_schooljaar = any(kw in kn for kw in SCHOOLJAAR_KOLOMNAMEN)

    if is_schooljaar:
        def _sj(jaar: int) -> str:
            return f"{jaar}/'{str(jaar + 1)[2:]}"
        if s == e:
            return _sj(s)
        return f"{_sj(s)}-{_sj(e)}"
    else:
        if s == e:
            return str(s)
        return f"{s}-{e}"


# ---------------------------------------------------------------------------
# Netwerk-helpers
# ---------------------------------------------------------------------------

def _is_html_response(tekst: str) -> bool:
    """Detecteer of een response HTML is i.p.v. CSV."""
    stripped = tekst.lstrip()
    return stripped.startswith(("<!DOCTYPE", "<html", "<HTML", "<!doctype"))


def _haal_csv_periode(url: str, client: httpx.Client) -> tuple[int | None, int | None, str | None]:
    """Haal start- en eindjaar op uit een CSV-resource.

    Returns:
        (start_jaar, eind_jaar, kolom_naam)
    """
    try:
        start_resp = client.get(url, headers={"Range": "bytes=0-4000"})
        start_resp.raise_for_status()
        start_tekst = start_resp.text

        # Sla HTML-responses over (bijv. 404-pagina's of redirects naar webpagina)
        if _is_html_response(start_tekst):
            return None, None, None

        eind_resp = client.get(url, headers={"Range": "bytes=-3000"})
        # bytes=-3000 geeft de laatste 3000 bytes; 200 als Range niet ondersteund wordt
        eind_tekst = eind_resp.text

        # Detecteer jaar-kolomnaam voor formattering
        lines = [l for l in start_tekst.splitlines() if l.strip()]
        kolom_naam: str | None = None
        if lines:
            header_lijn = lines[0]
            sep = "," if "," in header_lijn else (";" if ";" in header_lijn else "\t")
            try:
                header = [c.strip().strip('"') for c in next(csv.reader(io.StringIO(header_lijn), delimiter=sep))]
                _, kolom_naam = _vind_jaar_kolom_index(header)
            except StopIteration:
                pass

        start_jaar, eind_jaar = _parse_jaar_range_uit_csv_fragment(start_tekst, eind_tekst)
        return start_jaar, eind_jaar, kolom_naam

    except (httpx.HTTPError, httpx.RequestError) as exc:
        print(f"    [WARN] CSV ophalen mislukt: {exc}", file=sys.stderr)
        return None, None, None


# ---------------------------------------------------------------------------
# Update-functie
# ---------------------------------------------------------------------------

def update_duo(path: Path) -> int:
    """Verwerk duo_resources.json: vervang generiek periode-veld.

    Returns:
        Aantal bijgewerkte entries.
    """
    data: list[dict] = json.loads(path.read_text(encoding="utf-8"))

    bijgewerkt = 0

    with httpx.Client(timeout=20, follow_redirects=True) as client:
        for entry in data:
            ckan_id = entry.get("_ckan_id", "?")
            resources: list[dict] = entry.get("_resources", [])

            # Zoek de eerste echte CSV-resource (sla changelog/controle over)
            csv_resource = None
            for r in resources:
                naam_lower = r.get("naam", "").lower()
                fmt = r.get("format", "").upper()
                if fmt in ("CSV", "") and not any(
                    kw in naam_lower for kw in ("changelog", "controle", "toelichting", "readme")
                ):
                    csv_resource = r
                    break

            if csv_resource is None:
                continue

            url = csv_resource.get("url", "")
            if not url:
                continue

            start_jaar, eind_jaar, kolom_naam = _haal_csv_periode(url, client)
            periode_str = _formatteer_periode(start_jaar, eind_jaar, kolom_naam)

            if periode_str:
                oud = entry.get("periode", "")
                entry["periode"] = periode_str
                print(f"  {ckan_id}: {oud!r} → {periode_str!r}")
                bijgewerkt += 1
            else:
                print(f"  {ckan_id}: geen jaarinfo gevonden, ongewijzigd")

            # Korte pauze om de server niet te overbelasten
            time.sleep(0.3)

    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return bijgewerkt


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    root = Path(__file__).parent.parent / "src" / "riodata" / "data"
    duo_path = root / "duo_resources.json"

    print(f"Periodes ophalen voor {duo_path}…\n")
    n = update_duo(duo_path)
    print(f"\nKlaar: {n} entries bijgewerkt → {duo_path}")
