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

## Tegen de testomgeving (synthetische controle, #169)

Dezelfde runner draait tegen een draaiende omgeving, als controle van buiten de antwoordketen:

```bash
npm ci --ignore-scripts                                   # Playwright en ws, vastgezet in package.json
EVAL_BASE_URL=https://onderwijsdata-chat.test.sdp.surf.nl EVAL_USERNAME=… EVAL_PASSWORD=… \
TEST_MODELS=azure_ai/claude-sonnet-5-5 TEST_REPEATS=3 \
  npx playwright test real-questions --config=playwright.eval.config.js
```

`playwright.eval.config.js` start geen webserver en geen browser; de inloggegevens komen uit de omgeving,
nooit uit de repo. De CI-job `eval:bronwaarheid` (`.gitlab-ci.yml`) doet hetzelfde, gepland of met de hand,
met `EVAL_BASE_URL`, `EVAL_USERNAME` en `EVAL_PASSWORD` als (masked) CI-variabelen, en bewaart
`eval_results/` 90 dagen als artifact. Elke beurt kost een modelaanroep op die omgeving.

Los daarvan pingt de geplande CI-job `bron:ping` (`scripts/bronping.py`) elke bron één keer door de toollaag van de
chat, met de selecties van deze ijkpunten en zonder waarden te vergelijken: alleen of de bron nog antwoordt (#627).

## De rapporteval (#752)

`tests/e2e/rapport-bijsturing.spec.js` toetst of een rapport de bijsturing uit het gesprek volgt. Per scenario
(`tests/e2e/rapportscenarios.json`) speelt de runner een gesprek over één verbinding (`gesprek.js`): de sessie
hoort bij de socket. Daarna vraagt hij het rapport op met de onderzoeksvraag die de app voorstelt (#751). Dat gaat
met dezelfde functie als de app (`frontend/src/onderzoeksvraagVoorstel.js`). De controles lezen wat code vastlegde,
niet wat het model erover schreef (`rapportscore.js`):

- of de onderzoeksvraag de bevestigde is;
- wat de onderzoeksvraag noemt;
- de bronregel van elke grafiek, met dataset en bestand;
- de reeksnamen en categorieën in elke grafiek.

Per scenario komt het aantal geslaagde runs, met de reden van elke mislukte run, in `eval_results/rapport-<datum>.json`.

```bash
EVAL_BASE_URL=… EVAL_USERNAME=… EVAL_PASSWORD=… TEST_MODELS=azure_ai/claude-sonnet-5-5 TEST_REPEATS=3 \
  npx playwright test rapport-bijsturing --config=playwright.eval.config.js
```

`eval:bronwaarheid` draait hem mee. Per run kost dat twee of drie chatbeurten plus een rapport. De controles zelf
toetst `node --test tests/e2e/rapport-unit.mjs`, zonder app en zonder model; de job `frontend` draait die test.
