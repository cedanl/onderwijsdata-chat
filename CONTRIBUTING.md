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

## Testen en linten

Draai dit vóór je een merge request opent; de pipeline doet hetzelfde en blokkeert op falen.

```bash
uv run ruff check .                          # lint (backend)
uv run ruff format --check .                 # opmaak; `uv run ruff format .` herstelt het
uv run python scripts/ty_baseline.py         # typecheck: faalt alleen op nieuwe ty-diagnostics
uv run pytest tests/ -q                      # backend, zonder netwerk
cd frontend && npm run lint && npm test      # lint en tests (frontend)
```

De backendtests halen niets live op bij DUO of CBS: de pytest-job blokkeert elke MR en mag niet rood
worden door een storing bij een bron (#766). Het DUO-register en de dashboards draaien op bevroren
bestanden in `tests/fixtures/duo/` (fixture `duo_fixtures` in `tests/conftest.py`). Ververs ze met
`uv run python scripts/duo_testfixtures.py` als een test een ander DUO-bestand of een andere instelling
nodig heeft. Of de bronnen zelf nog antwoorden, controleert `bron:ping` (`scripts/bronping.py`, wekelijks).

`ty-baseline.txt` bevat de ty-diagnostics die er al waren. Los je er een paar op, draai dan
`uv run python scripts/ty_baseline.py --update` en commit de kleinere baseline mee. Werk de
baseline niet bij om een nieuwe diagnostic weg te krijgen; los die op.

De baseline krimpt per kwartaal naar nul (`AFBOUWPLAN` in `scripts/ty_baseline.py`, #391):
≤100 eind 2026, ≤70 eind Q1 2027, ≤40 eind Q2 en 0 eind Q3 2027. Het script meldt bij elke run
hoeveel er nog af moet.

De GitHub-workflow draait dezelfde poorten. GitLab blijft de bron: GitHub spiegelt `main` en alle tags;
er draait daar geen deploy meer.

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
