# Determinisme als CI-eigenschap (#347)

Wat niet wordt gemeten raakt verloren bij de eerstvolgende promptwijziging. Deze meting
bewaakt, zonder netwerk en zonder model, dat de normalisatielaag (#342) en het gesloten
selectieschema (#343) blijven doen wat ze beloven: dezelfde selectie in een andere
spelling is dezelfde selectie.

Aanvulling op de gouden set voor zoeken (`tests/test_catalog_gouden_set.py`, #33), de
retrieval-baseline (#359) en de modelroute-evals (#190); geen duplicaat daarvan.

## Bestanden

| Bestand | Inhoud |
|---|---|
| `harnas.py` | de gevallenset, fixtures, digests, herstelgraad en de scorekaart |
| `varianten.py` | seeded generator van gelijkwaardige spellingen per aanroep |
| `gevallen.json` | de golden stand: per geval plan-digest, compilaat en uitkomst-digest, met herkomst |
| `test_determinisme.py` | de poorten in CI |
| `scripts/meet_determinisme.py` | het rapport op de commandoregel en `--schrijf-golden` |

## Metingen en poorten

- **Plan-invariantie**: per geval worden 40 gelijkwaardige spellingen gegenereerd
  (sleutelvolgorde, `__eq`/`__in`-vormen, waardenkast, lijstvolgorde en -dubbelen,
  periodespelling, data_key-spelling, OData-spatiëring, defaults). Poort: 1 unieke
  plan-digest per geval, en verschillende gevallen delen er geen.
- **Golden stand**: plan-digest, het compilaat van een gesloten selectie en de
  uitkomst-digest van uitvoerbare gevallen staan vast in `gevallen.json`. Een wijziging
  vereist een expliciete update (`--schrijf-golden`) met een verantwoording in de MR.
- **Reparatie-/weigeringsgraad**: wat de periodeherstelroute op een vaste sample doet;
  per geval gepoort. Live geven de logregels `PERIODE_HERSTEL` en `PERIODE_WEIGERING`
  (tools/query.py) dezelfde telling per antwoord, zodat de reparatiegraad over echte
  runs te volgen is (de drempel "repair dalend" uit #347 is een trend, geen CI-poort).

## Herkomst

De scorekaart draagt `prompt_hash` (hash van `prompts/system.md`), het geconfigureerde
`model` en de `schema_digest` van de toolschema's: zo is elke meting toe te schrijven aan
een prompt- en modelversie. Plannen zijn modelvrij, dus een promptwijziging verandert de
digests niet; het rapport meldt een afwijkende promptversie informatief.

## Buiten deze meting

Stapvariantie per vraagklasse (p50/p95) en de tijd tot het eerste controleerbare getal
uit #347 zijn metingen op echte runs (telemetrie), geen CI-eigenschap; de `CONTROLES`-
en `HERKANSING`-logregels (#409) en de herstel-logregels hierboven leveren er de data
voor. De vaste plannen voor startvragen horen bij #348.

## Draaien

```bash
uv run pytest tests/determinisme -q
uv run python scripts/meet_determinisme.py                   # rapport
uv run python scripts/meet_determinisme.py --schrijf-golden  # opnieuw vastleggen
```
