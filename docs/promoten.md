# Promoten naar playground

De ladder heeft twee sporten: **test** en **playground**. `development` en
`production` doen er niet aan mee (geen live URL, respectievelijk nog niet live).

| Omgeving | Beweegt wanneer | Pin in `helmrelease.yaml` |
|---|---|---|
| `test` | elke push naar `main`, vanzelf | open range `>=0.0.1-0.0` |
| `playground` | alleen door jouw promotie-MR | vaste release, bijv. `"2.0.0"` |

Eerst zie je een wijziging op test; pas als jij het goed vindt, promoveer je naar
playground. Een tag deployt zelf niets: de pin is de deploy.

## Release maken

0. **Vóór de tag**, in de laatste MR naar `main` (#679, #684):
   - `version` in `pyproject.toml` (en `uv lock`) en `CITATION.cff` (`version`, `date-released`) op de nieuwe release;
   - in `CHANGELOG.md` wordt "Niet uitgebracht" de kop `## X.Y.Z — <datum>`, met een nieuwe lege "Niet uitgebracht"
     erboven, en de kopzin noemt de nieuwe laatste tag;
   - groen of bewust geaccepteerd: `bron:ping` (`scripts/bronping.py`), `scripts/ijkwaarden.py`, `audit:python` en
     `audit:npm` in de pipeline;
   - een recente `eval:bronwaarheid`-run (#692): de uitslag van de bronwaarheid-evals tegen test. De job is
     informatief (`allow_failure`) en blokkeert dus niets; deze stap is de enige borging. Start hem met "Run pipeline"
     op `main` (de job staat dan op handmatig en vraagt de CI-variabelen `EVAL_BASE_URL`, `EVAL_USERNAME` en
     `EVAL_PASSWORD`); het slagingspercentage per model en vraag staat in het artifact
     `eval_results/slagingspercentage-<datum>.json` (90 dagen bewaard). Zet het totaal in de beschrijving van die laatste
     MR (of, bij een promotie van een bestaande release, van de promotie-MR). Staat er een rode kritieke vraag (`ijk-*` of `weigering-*`) in, los die dan eerst op of noem in de MR
     waarom je hem bewust accepteert.
1. Wacht tot de pipeline van `main` groen is. Zonder groene pipeline publiceert
   `version:promote` geen chart.
2. Tag kaal, **zonder `v`**: SDP matcht `^[0-9]+\.` op de ref-naam, dus `v2.1.0`
   is onzichtbaar (geen basis voor het versienummer, geen chart).

   ```bash
   git checkout main && git pull
   git tag 2.0.0 && git push origin 2.0.0
   ```
3. De tag-pipeline publiceert de schone chart `2.0.0` en `sync:github` spiegelt
   de tag naar GitHub. Maak daar daarna de GitHub-release.

## Naar playground promoveren

```bash
git checkout main && git pull
git checkout -b chore/promote-playground
uv run python scripts/promotie.py promote              # nieuwste release-tag
uv run python scripts/promotie.py promote --version 2.0.0   # of een specifieke
git commit -am "chore: promote playground to 2.0.0"
git push -u origin chore/promote-playground
glab mr create --fill
```

Het diff is één regel. Na de merge pakt Flux de pin binnen ~1 minuut op.

Controleer daarna of het cluster echt is verplaatst:

```bash
kubectl --context playground get helmrelease onderwijsdata-chat \
  -n services-onderwijsdata-chat \
  -o jsonpath='{.spec.chart.spec.version} -> {.status.history[0].chartVersion}'
curl https://<playground-url>/version   # "version" = release-tag, "commit" = gebouwde commit
```

Leg het vast met een marker; die start geen pipeline:

```bash
uv run python scripts/promotie.py mark
git push origin env/playground/2.0.0
```

## De poort in CI

`env:promotion-ladder` draait op MR's en `main` en faalt wanneer:

- `test` geen open range meer heeft;
- `playground` geen vaste `X.Y.Z` pint (een range of rc-build);
- de gepinde release-tag niet op de remote bestaat (de chart bestaat dan ook niet).

## Jaarlijks

Loop eens per jaar [Operatie](operatie.md), [Deployment](deployment.md), `manifests/README.md` en
[Test Environment](test-environment.md) na tegen de manifests en het cluster (replica's, resources, ingress, ladder).
Ze liepen eerder een jaar achter (#679).

## Nooit

- Playground niet terugzetten op een range: dan volgt het weer elke main-build.
- Geen `v`-prefix op release-tags.
- Niet taggen voordat `main` groen is.
