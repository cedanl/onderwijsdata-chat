# Metamorfe tests voor de rekentools (#1263)

IJkwaarden (`tests/ijkwaarden/`) en gouden tests (`tests/test_gouden_*.py`) toetsen losse getallen, en de
determinismemeting (`tests/determinisme/`) toetst dat dezelfde vraag in een andere spelling hetzelfde plan geeft. Wat
geen van die drie toetst, zijn de **relaties** tussen uitkomsten: de delen tellen op tot het totaal, een jaar uit een
reeks is hetzelfde als dat jaar alleen, een verschil is het verschil van twee losse jaren. Zo'n relatie kent de juiste
uitkomst niet; ze vangt een fout die beide kanten niet even groot maakt.

Alles draait op bevroren, verzonnen fixtures met de vorm van de bron (DUO met `-1` voor een onderdrukte cel, CBS met
een totaalcode per dimensie en een lege cel), zonder netwerk: het netwerkblok van `tests/netwerkblok.py` geldt
gewoon. De getallen komen uit `random.Random` met een vaste seed.

## Bestanden

| Bestand | Inhoud |
|---|---|
| `harnas.py` | de fixtures in de store (DUO, CBS, fusie, get_maat, koppel_data) en het lezen van de JSON-uitkomsten naar getallen |
| `relaties.py` | de relaties: elk een functie die faalt als de relatie breekt, met haar soort, tool en bron |
| `test_relaties.py` | elke relatie als test, en de dekking per soort (DUO en CBS) |
| `test_scherpte.py` | elke relatie tegen drie opzettelijk kapotte varianten van de tools |

## Relaties

| Relatie | Wat gelijk moet zijn | Tool | Bron |
|---|---|---|---|
| Delen en totaal | som over sectoren of leerwegen = het totaal van dezelfde selectie zonder uitsplitsing; mannen + vrouwen = de totaalcode | `query_data`, `get_maat` (voltijd + deeltijd + duaal = alle), `koppel_data` (de som na de koppeling = die van de tabel) | DUO, CBS |
| Sectoren en landelijk | mbo + hbo + wo = het landelijke bestand, waar de bron additief is; bij een niet-additieve CBS-maat (hbo + wo > HO-totaal, `tools/cbs_meta.py`) juist geen gelijkheid, en de som over de onderwijssoorten of over een %-kolom wordt geweigerd (`tools/optelbaar.py`) | `query_data`, `compute_kpi` | DUO, CBS |
| Reeks en los jaar | jaar n uit een reeks = dezelfde vraag voor alleen jaar n, ook in een andere schooljaarspelling | `query_data`, `get_maat` | DUO, CBS |
| Volgorde | een andere rijvolgorde van de bron of van de filterwaarden geeft hetzelfde resultaat | `query_data`, `koppel_data` | DUO, CBS |
| Fusie | A + B vóór de fusie = de opvolger na omrekening, waar DUO omrekent (#728), met de vaste fusieregel op de selectie; in DUO's verantwoording uit XBRL (geen omrekening, #935) is de opvolger alleen zichzelf en zegt de regel dat | `query_data` | DUO |
| Verschil | `compute_kpi` delta van jaar a tot b = waarde b - waarde a uit `query_data` | `compute_kpi` | DUO, CBS |
| Onderdrukte cel | met een onderdrukte cel (DUO `-1`, CBS `'.'`) is de som een ondergrens: som ≤ totaal, nooit gelijk, met het label `<kolom> (onderdrukte cellen)` en de ondergrensnoot uit `tools/duo.py` | `query_data` | DUO, CBS |

## Scherpte

`test_scherpte.py` draait elke relatie tegen een opzettelijk kapotte variant (een monkeypatch, geen bronbestand
gewijzigd) en eist dat er per mutatie minstens één faalt. Stand bij #1263 (18 relaties):

| Mutatie | Monkeypatch | Falende relaties |
|---|---|---|
| -1 niet maskeren | `tools.store.mask_sentinels` laat `-1` staan | 1: `onderdrukt_duo` |
| rij dubbel tellen | `tools.query._som_of_leeg` telt de eerste rij van elke groep twee keer | 8: `delen_en_totaal_duo`, `sectoren_en_landelijk_duo`, `delen_en_totaal_maat`, `delen_en_totaal_koppel`, `fusie_duo_rekent_om`, `fusie_xbrl_rekent_niet_om`, `onderdrukt_duo`, `onderdrukt_cbs` |
| jaar verschuiven | `tools.query._apply_filters` leest bij een filter op de periodekolom het jaar ervoor | 7: `sectoren_en_landelijk_duo`, `reeks_en_los_jaar_duo`, `reeks_en_los_jaar_cbs`, `reeks_en_los_jaar_maat`, `verschil_duo`, `verschil_cbs`, `onderdrukt_duo` |

De test print deze telling bij elke run (`pytest tests/metamorf/test_scherpte.py -q`).

## Een relatie toevoegen

Een nieuwe rekentool krijgt minstens één relatie hier (CONTRIBUTING.md, "Testen en linten"). Schrijf een functie in
`relaties.py` met `@relatie(soort, tool, bron)`; ze zet haar eigen fixtures in de store en faalt met `assert`.
`test_relaties.py` en `test_scherpte.py` pakken haar vanzelf op. Breekt een relatie in de tool echt, dan is dat een
apart issue: geef de relatie dan `breekt="#<issue>"` mee (`@relatie(soort, tool, bron, breekt="#<issue>")`), zodat
haar test `xfail` (strict) is met die verwijzing, en verander de tool niet in dezelfde MR.

## Draaien

```bash
uv run pytest tests/metamorf -q --durations=5
```
