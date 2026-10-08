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
uv run pytest tests/ -q                      # backend; test_instellingen.py laadt live DUO-data en is traag
cd frontend && npm run lint && npm test      # lint en tests (frontend)
```

`ty-baseline.txt` bevat de ty-diagnostics die er al waren. Los je er een paar op, draai dan
`uv run python scripts/ty_baseline.py --update` en commit de kleinere baseline mee. Werk de
baseline niet bij om een nieuwe diagnostic weg te krijgen; los die op.

De baseline krimpt per kwartaal naar nul (`AFBOUWPLAN` in `scripts/ty_baseline.py`, #391):
≤100 eind 2026, ≤70 eind Q1 2027, ≤40 eind Q2 en 0 eind Q3 2027. Het script meldt bij elke run
hoeveel er nog af moet.

De GitHub-workflow draait dezelfde poorten. GitLab blijft de bron: GitHub spiegelt `main` en alle tags;
er draait daar geen deploy meer.

Werk test-first: schrijf de test die het gedrag vastlegt, laat hem falen, en maak hem dan groen.
Houd functies klein en met één verantwoordelijkheid, en ruim dode code op die je tegenkomt.

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

## Geheimen

Zet nooit API-keys of wachtwoorden in de repo. Lokaal staan ze in `.env` (niet in git); voor
omgevingen gebruiken we SOPS-versleutelde secrets.

## Een fout antwoord melden

Gebruik de issue-template "Verkeerd antwoord gekregen": noem de vraag, het model, de dataset en
het antwoord dat je verwachtte. Met die vier gegevens is het meestal te reproduceren.
