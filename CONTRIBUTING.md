# Bijdragen aan onderwijsdata-chat

Fijn dat je meewerkt. Deze pagina zegt hoe je de app draait, hoe je test en hoe een wijziging
in `main` komt.

## Opzetten

```bash
uv sync --group dev           # backend en dev-tools
cd frontend && npm ci         # frontend
cp .env.example .env          # MODEL en de bijbehorende API-key invullen
make dev                      # backend en frontend samen
```

De bronpakketten `onderwijsdata` (CBS) en `riodata` (RIO, DUO, UWV, ROA, Inspectie, SBB) staan in deze repo, onder
`packages/`, als leden van een uv-workspace (#883, #885). Het zijn aparte pakketten met een eigen `pyproject.toml` en
eigen tests, maar ze delen met de chat één `uv.lock` en één `.venv`: `uv sync` installeert ze *editable*, dus een
wijziging in `packages/` is direct zichtbaar in de chat. Draai na een pull die `pyproject.toml`, `uv.lock` of
`packages/` raakt opnieuw `uv sync`. Een `.venv` van vóór #885 heeft de pakketten nog als git-installatie.

De tests van een pakket draai je in de map van dat pakket, elk pakket apart (beide hebben een `tests/__init__.py`,
dus in één run botsen de modulenamen):

```bash
uv run --directory packages/onderwijsdata pytest -q -rs
uv run --directory packages/riodata pytest -q -rs
```

Dezelfde twee regels staan in de CI-job `pytest`, vóór de chattests (#886). Tests die het netwerk raken staan achter
`RIODATA_LIVE=1` en slaan over, zoals in de pakketrepo's; zet die variabele alleen lokaal, bijvoorbeeld voor
`RIODATA_LIVE=1 uv run --directory packages/riodata pytest tests/test_rio_live.py`.

**De grens tussen pakket en chat** bewaakt `tests/test_importgrens.py` (draait mee met `pytest tests/`): een pakket
importeert de chat (`tools`, `agent`, `core`, `routes`, `persistence`, …) en het andere pakket niet, en de chat
importeert alleen de publieke API van een pakket, dus niets met een underscore in het pad (`riodata.duo` wel,
`riodata._catalog` niet). Ophalen en bronlogica horen in `packages/`, beleid (scope, poorten, etiketten) in `tools/`.

**Ruff en ty slaan `packages/` over, bewust.** De pakketten hadden als losse repo's geen lint of typecontrole: ruff
geeft er 248 bevindingen en wil 93 bestanden anders opmaken, ty geeft 93 diagnostics. Opnemen zou `ty-baseline.txt`
(nu 78) boven het plafond van het afbouwplan (≤100 eind 2026, #391) tillen en de `git blame` van de pakketten
overschrijven met een opmaakcommit. De dekking van de chat (`fail_under`) telt de pakketregels ook niet mee; de
pakkettests laten hun eigen dekking zien in het log. Wil je een pakket opruimen, doe dat per pakket in een eigen MR
(ruim eerst de bevindingen op, haal het pakket dan uit `extend-exclude` en `[tool.ty.src]` in `pyproject.toml`).

## Testen en linten

Draai dit vóór je een merge request opent; de pipeline doet hetzelfde en blokkeert op falen.

```bash
uv run ruff check .                          # lint (backend)
uv run ruff format --check .                 # opmaak; `uv run ruff format .` herstelt het
uv run python scripts/ty_baseline.py         # typecheck: faalt alleen op nieuwe ty-diagnostics
uv run pytest tests/ -q                      # backend, zonder netwerk
cd frontend && npm run lint && npm test      # lint en tests (frontend)
```

Tests met de marker `live` praten met het echte model en de bronnen; `pytest tests/` slaat ze over (`addopts` in
`pyproject.toml`, #831). Draai ze apart: `uv run --env-file .env pytest -m live tests/`.

De backendtests halen niets live op bij DUO of CBS: de pytest-job blokkeert elke MR en mag niet rood
worden door een storing bij een bron (#766). Het DUO-register en de dashboards draaien op bevroren
bestanden in `tests/fixtures/duo/` (fixture `duo_fixtures` in `tests/conftest.py`). Ververs ze met
`uv run python scripts/duo_testfixtures.py` als een test een ander DUO-bestand of een andere instelling
nodig heeft. Of de bronnen zelf nog antwoorden, controleert `bron:ping` (`scripts/bronping.py`, dagelijks).

**Uitgaand netwerk is dicht in de tests** (#915). `tests/conftest.py` zet het netwerkblok van `tests/netwerkblok.py`
aan voor de hele run: een DNS-vraag of verbinding naar een host buiten deze machine faalt met `NetwerkGeblokkeerd`
("uitgaand netwerk naar data.overheid.nl is dicht in tests: markeer de test als live of gebruik een fixture"). Vangt
de code die fout op en valt ze terug, dan faalt de test daarna alsnog met dezelfde melding: zo'n pad hing in CI af van
het netwerk van de runner. Localhost, 127.0.0.0/8, ::1 en Unix-sockets blijven open (TestClient, lokale testservers,
een Postgres op dezelfde host); subprocessen zoals `helm` en `uv build` vallen erbuiten. Alleen een test met de
marker `live` mag naar buiten. De pakketten hebben dezelfde module in `packages/<naam>/tests/` (ze importeren de chat
niet); daar zet `RIODATA_LIVE=1` het blok open. `tests/test_netwerkblok.py` bewaakt het blok en dat de kopieën gelijk
blijven.

De rekenende tools (get_maat, get_mbo_indicatoren, get_accreditatie, get_inspectieoordeel(_vo), UWV/ROA, compute_kpi)
hebben gouden tests met verwachte getallen in `tests/test_gouden_*.py`, op bevroren bronnen in
`tests/fixtures/gouden/` (fixture `gouden`; #870). `bronnen.json` noemt per bestand de
bron en de ophaaldatum. Ververs ze met `uv run python scripts/gouden_testfixtures.py` en reken de verwachte waarden
daarna opnieuw na met pandas op de nieuwe bestanden (de berekening staat bij elke test).

`ty-baseline.txt` bevat de ty-diagnostics die er al waren. Los je er een paar op, draai dan
`uv run python scripts/ty_baseline.py --update` en commit de kleinere baseline mee. Werk de
baseline niet bij om een nieuwe diagnostic weg te krijgen; los die op.

De baseline krimpt per kwartaal naar nul (`AFBOUWPLAN` in `scripts/ty_baseline.py`, #391):
≤100 eind 2026, ≤70 eind Q1 2027, ≤40 eind Q2 en 0 eind Q3 2027. Het script meldt bij elke run
hoeveel er nog af moet.

De poorten draaien alleen in GitLab CI (`.gitlab-ci.yml`). GitLab blijft de bron: GitHub spiegelt `main` en alle
tags. Op GitHub draait alleen de docs-workflow (`.github/workflows/docs.yml`: `mkdocs build --strict` en publicatie
naar Pages); er draait daar geen test en geen deploy.

De pipeline faalt als de dekking van `pytest` onder `fail_under` in `pyproject.toml` komt (#691). Dek je nieuwe code
met tests in plaats van de drempel te verlagen; na een merge die de stand duidelijk verbetert, mag de drempel omhoog
(afgerond naar beneden op de stand van `main`), nooit omlaag.

Werk test-first: schrijf de test die het gedrag vastlegt, laat hem falen, en maak hem dan groen.
Houd functies klein en met één verantwoordelijkheid, en ruim dode code op die je tegenkomt.

## Een antwoordcontrole toevoegen

Het antwoordpad groeit met elke controle (zie [de stroomkaart](docs/anti-hallucination-architecture.md)
en ADR-007). Een nieuwe controle in `antwoordcontrole` (`agent/controles.py`) of een andere poort in dat pad heeft vier dingen,
in de MR-beschrijving en waar mogelijk in de docstring:

1. **Foutklasse:** welke fout vangt hij, met een echt voorbeeld (een antwoord, een issue of een evalcase).
2. **Eigenaar:** de module waar hij thuishoort, en wie hem onderhoudt als de bron of het model verandert.
3. **Test:** een test die zonder de controle faalt, en een test dat hij een correct antwoord niet afkeurt.
4. **Heroverwegingscriterium:** wanneer hij weg mag, bijvoorbeeld "het model maakt deze fout niet meer in de eval" of
   "vuurt een kwartaal lang niet af".

Zet een controle liefst als pure functie (invoer → bevindingen) en houd het streamen en publiceren daarbuiten.

**Kwartaalreview, verwijderen of vereenvoudigen.** Eens per kwartaal kijk je welke controles niet meer afgaan. De logregel
`CONTROLES` toont per antwoord welke controle wat gaf (CH-01), dus de afvuurfrequentie is te tellen. Een controle zonder
afgaan én zonder heroverwegingscriterium dat nog geldt, is een kandidaat om te verwijderen; zet daar een issue voor open.

## Taal

- **Documentatie en commentaar:** Nederlands, ook in nieuwe ADR's. Vertaal bestaande Engelse tekst niet in bulk; de regel
  geldt voor tekst die je nieuw schrijft of herschrijft.
- **Identifiers:** volg de code om je heen. Het domein (instellingen, schooljaren, bronnen) heeft Nederlandse termen; houd
  die gelijk aan de termen in de gebruikersinterface en de bron, en maak er geen tweede, Engelse naam naast.
- **Commits en issues:** Nederlands, zie hieronder.

## Commits

We gebruiken [Conventional Commits](https://www.conventionalcommits.org/) met een Nederlandse
omschrijving: `fix(agent): teleenheidcontrole slaat niet aan op een ontkenning (#214)`.

- Eén wijziging per commit, met in de body wat er veranderde en waarom.
- Houd app-code en ops-wijzigingen (Kubernetes, SOPS, Docker) in aparte commits.
- Verwijs naar het issue met `Refs #N`. Sluit het issue pas als de wijziging in `main` staat.

## Merge requests

- Maak een branch vanaf `main` en open een merge request naar `main` (GitLab is de bron; GitHub is een mirror).
- Vul de template in: wat verandert er, welke tests heb je gedraaid, wat heb je bewust niet gedaan.
- Een MR met alleen groene tests en een duidelijke omschrijving is makkelijk te beoordelen. Zet
  auto-merge pas aan als de pipeline draait.
- Merkt een gebruiker of beheerder de wijziging, zet dan een changelog-item in `changelog.d/` (hieronder).

## Changelog

Een MR zet zijn changelog-item niet in `CHANGELOG.md`, maar in een eigen bestand in `changelog.d/`:
`changelog.d/<issuenummer>-<onderwerp>.md`, bijvoorbeeld `changelog.d/797-changelog-fragmenten.md`. Zo raken twee
MR's nooit hetzelfde bestand, en botsen ze niet bij een rebase of in de merge train (#797). Het bestand heeft de vorm
van een item in `CHANGELOG.md`: een `###`-kopje met het issuenummer, met bullets eronder.

```markdown
### Een hernoemd gesprek houdt zijn titel (#757)
- Wat de gebruiker of beheerder merkt, en waarom.
```

- De naam begint met het issuenummer; raakt de MR meer issues, neem dan het hoofdissue. Daarna kleine letters, cijfers
  en streepjes.
- Geen kop van niveau 1 of 2 (`#`, `##`): die zet het releasescript.
- `tests/test_changelog.py` controleert in elke MR de naam en de vorm van de fragmenten.

Bij een release zet `scripts/changelog.py` de fragmenten onder de versiekop in `CHANGELOG.md`, hoogste issuenummer
bovenaan, en verwijdert ze ([Promoten](docs/promoten.md), stap 0).

## Geheimen

Zet nooit API-keys of wachtwoorden in de repo. Lokaal staan ze in `.env` (niet in git); voor
omgevingen gebruiken we SOPS-versleutelde secrets.

## Een fout antwoord melden

Gebruik de issue-template "Verkeerd antwoord gekregen": noem de vraag, het model, de dataset en
het antwoord dat je verwachtte. Met die vier gegevens is het meestal te reproduceren.
