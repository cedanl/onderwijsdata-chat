# IJkwaarden voor de bronwaarheid-evals (#190)

De evals in `tests/e2e/evaluations.json` toetsen antwoorden op natuurlijke, ongehulpte vragen tegen
waarden die **rechtstreeks bij de bron** zijn opgehaald: CBS via de OData-feed (httpx), DUO en RIO
via het `riodata`-package. Niet via `tools/`: een fout in de tools mag de ijkwaarde niet mee
veranderen.

## Bestanden

| Bestand | Rol |
|---|---|
| `harnas.py` | de lijst ijkpunten (`IJKPUNTEN`), het ophalen per bron, de vergelijking en het schrijven |
| `scripts/ijkwaarden.py` | de opdrachtregel: ophalen, verschillen tonen, met `--schrijf` vastleggen |
| `tests/e2e/ijkwaarden.json` | de vastgelegde stand: per id bron, selectie, eenheid, schooljaar, CBS-status, waarde, URL en ophaaldag |
| `tests/e2e/ijkwaarden.js` | vult `data_points.reference_values` van een eval uit de fixture (`data_points.ijkwaarden`) |
| `test_ijkwaarden.py` | de mechaniek zonder netwerk, en de consistentie tussen lijst, fixture en evals |

## Werkwijze

```bash
uv run python scripts/ijkwaarden.py            # ophalen en elk verschil met de fixture tonen (exit 1 bij verschil)
uv run python scripts/ijkwaarden.py --schrijf  # de nieuwe stand vastleggen; verantwoord dat in de MR
```

Het script neemt nooit stil een nieuwe waarde over. CBS herziet voorlopige cijfers en DUO publiceert
een nieuwe jaargang: zo'n wijziging is een bewuste stap in een MR, met de oude en nieuwe waarde in
het rapport, in plaats van een eval die stil gaat falen.

## Definities

- **DUO**: som van de kolom over de rijen van instelling, opleidingsvorm en studiejaar in het bestand
  met `OPLEIDINGSVORM` (resource 3). Een `-1` is een onderdrukte cel (1–4) en telt niet mee; de som is
  dan een ondergrens en het aantal zulke cellen staat bij de waarde (`onderdrukte_cellen`).
- **Eenheid**: `p01hoinges` telt personen (hoofdinschrijvingen), `p03hoinschr` inschrijvingen,
  `p02ho1ejrs` eerstejaars personen. "Studenten" is personen; inschrijvingen alleen op expliciete vraag.
- **CBS**: één cel uit `TypedDataSet` met elke dimensie gepind; het filter gebruikt `trim()` omdat CBS
  de sleutels van een dimensie opvult tot één breedte (#531). De status komt uit `Perioden.Status`.
- **RIO**: de erkende onderwijsinstelling met deze volledige naam op de dag van ophalen, en de
  vestigingen eronder via de hiërarchische instellingsrelaties; de plaats staat achter de `;` in de naam.

## In de evals

Een eval verwijst per sleutel (jaar of 'totaal') naar een id: `"data_points": {"ijkwaarden": {"2024":
"cbs-hbo-voltijd-2024"}}`. De runner en `score-unit.mjs` vullen daaruit `reference_values`; een
ijkwaarde is exact (`tolerance_pct` 0). Eenheid, schooljaar en status toetst de eval met `must_mention`
("personen", "voorlopig", "definitief") naast de waarde zelf.
