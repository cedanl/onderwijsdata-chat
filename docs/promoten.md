# Promoten naar playground

De ladder heeft twee sporten: **test** en **playground**. `development` en
`production` doen er niet aan mee (geen live URL, respectievelijk nog niet live).

| Omgeving | Beweegt wanneer | Pin in `helmrelease.yaml` |
|---|---|---|
| `test` | elke push naar `main`, vanzelf | open range `>=0.0.1-0.0` |
| `playground` | alleen door jouw promotie-MR | vaste release `"X.Y.Z"` |

Eerst zie je een wijziging op test; pas als jij het goed vindt, promoveer je naar
playground. Een tag deployt zelf niets: de pin is de deploy.

## Release maken

0. **Vóór de tag**, in de laatste MR naar `main` (#679, #684):
   - `version` in `pyproject.toml` (en `uv lock`) en `CITATION.cff` (`version`, `date-released`) op de nieuwe release;
   - `uv run python scripts/changelog.py X.Y.Z` zet de changelog-fragmenten uit `changelog.d/` onder de kop
     `## X.Y.Z — <datum>` in `CHANGELOG.md`, direct onder "Niet uitgebracht", en verwijdert ze (#797). Items die nog
     onder "Niet uitgebracht" staan, komen onder de fragmenten mee. Draai het eerst met `--droog`: dat toont de nieuwe
     versiesectie en schrijft niets. Die sectie (of daarna `git diff <vorige tag>..X.Y.Z -- CHANGELOG.md`) is de bron
     voor de release-omschrijving op GitHub (stap 3). De kopzin van `CHANGELOG.md` noemt de nieuwe laatste tag;
   - groen of bewust geaccepteerd: `bron:ping` (`scripts/bronping.py`), `scripts/ijkwaarden.py`, `audit:python` en
     `audit:npm` in de pipeline;
   - een recente `eval:bronwaarheid`-run (#692): de uitslag van de bronwaarheid-evals tegen test. De job is
     informatief (`allow_failure`) en blokkeert dus niets; deze stap is de enige borging. Start hem met "Run pipeline"
     op `main` (de job staat dan op handmatig en vraagt de CI-variabelen `EVAL_BASE_URL`, `EVAL_USERNAME` en
     `EVAL_PASSWORD`); het slagingspercentage per model en vraag staat in het artifact
     `eval_results/slagingspercentage-<datum>.json` (90 dagen bewaard). Zet het totaal in de beschrijving van die laatste
     MR (of, bij een promotie van een bestaande release, van de promotie-MR). Zet er de regel
     `kritiek …: N van M gehaald; rood: …` uit de joblog bij (besluit #693, #753). Kritiek zijn de ijk-cases, de weigeringen en het
     #742-paar (`expected.kritiek` in `tests/e2e/evaluations.json`):
     - een weigering moet in elke herhaling slagen;
     - een andere kritieke vraag in een meerderheid (2 van 3 bij `TEST_REPEATS=3`).

     De details per vraag, met de reden van elke mislukte run, staan in `eval_results/kritiek-<datum>.json`. Is er een
     kritieke vraag rood, dan wacht de promotie. Of de MR zegt waarom ze toch doorgaat.
1. Wacht tot de pipeline van `main` groen is. Zonder groene pipeline publiceert
   `version:promote` geen chart.
2. Tag kaal, **zonder `v`**: SDP matcht `^[0-9]+\.` op de ref-naam, dus `v2.1.0`
   is onzichtbaar (geen basis voor het versienummer, geen chart).

   ```bash
   git checkout main && git pull
   git tag X.Y.Z && git push origin X.Y.Z
   ```
3. De tag-pipeline publiceert de schone chart `X.Y.Z` en `sync:github` spiegelt
   de tag naar GitHub. Maak daar daarna de GitHub-release.

## Naar playground promoveren

```bash
git checkout main && git pull
git checkout -b chore/promote-playground
uv run python scripts/promotie.py promote              # nieuwste release-tag
uv run python scripts/promotie.py promote --version X.Y.Z   # of een specifieke
git commit -am "chore: promote playground to X.Y.Z"
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
git push origin env/playground/X.Y.Z
```

## De poort in CI

`env:promotion-ladder` draait op MR's en `main` en faalt wanneer:

- `test` geen open range meer heeft;
- `playground` geen vaste `X.Y.Z` pint (een range of rc-build);
- de gepinde release-tag niet op de remote bestaat (de chart bestaat dan ook niet).

## Bevriezing tijdens de overgang naar onderwijsbronnen

Besluit 04-11 (#890): de bronpakketten `riodata` en `onderwijsdata` gaan op in één pakket `onderwijsbronnen`
(#909–#914). Playground heeft bestaande gebruikers met opgeslagen gesprekken en recepten. Het nieuwe bron-ID-contract
gaat daar daarom pas aan als het op test én playground bewezen werkt.

Besluit 05-11 ([comment op #890](https://git.ia.surf.nl/surf-internal/npuls/ceda/onderwijsdata-chat/-/issues/890#note_1318539))
vervangt de bevriezing van 04-11: er komt geen aparte release vóór #910.

1. **#910, #911 en #912 gaan in één release naar playground**, met `BRON_ID_CONTRACT: "schaduw"` in
   `manifests/playground`, op dezelfde manier als in `manifests/test`. In schaduwmodus volgt het gedrag het oude pad;
   de app logt alleen waar het nieuwe contract zou afwijken. Volgorde: eval #909 (nulmeting) → merge #910+#911 en
   #912 → rooktest en eval op test → release → promotie-MR met de pin en de vlag. Na de promotie: `/health`,
   `/version`, en in de pod-log dat de schaduwmodus aan staat.
2. **Van die promotie tot de go in #913: de vlag blijft op `schaduw`**, op test en op playground. Pas na enkele
   dagen schaduwlog op beide omgevingen en de go van de gebruiker in #913 gaat de vlag naar `aan`.
3. **#914** haalt daarna de shims en het oude pad weg. Daarna vervalt deze sectie; haal haar weg in die MR.

## Jaarlijks

Loop eens per jaar [Operatie](operatie.md), [Deployment](deployment.md), `manifests/README.md` en
[Test Environment](test-environment.md) na tegen de manifests en het cluster (replica's, resources, ingress, ladder).
Ze liepen eerder een jaar achter (#679).

Rond 1 september: lees de tabel met het wettelijk collegegeld (`tools/collegegeld.py`, #729) na tegen artikel 9 van
de [Regeling financiën hoger onderwijs](https://wetten.overheid.nl/BWBR0024005), in de geldende versie en in een
aangekondigde wijziging (`https://wetten.overheid.nl/BWBR0024005/<datum>`). Voeg het nieuwe studiejaar toe met zijn
versie en ophaaldatum, zet de ophaaldatum van de nagelezen jaren bij, en werk de tabel in
[Databronnen](databronnen.md) en `tests/test_collegegeld.py` mee bij. Neem alleen bedragen op die in de wettekst
staan. `bron:ping` wordt rood zodra het lopende studiejaar ontbreekt.

## Nooit

- Playground niet terugzetten op een range: dan volgt het weer elke main-build.
- Niet pinnen op `2.0.0`: die tag heeft geen chart. `promotie.py promote` weigert hem.
- Geen `v`-prefix op release-tags.
- Niet taggen voordat `main` groen is.
- `BRON_ID_CONTRACT` in `manifests/playground` niet op `aan` zetten vóór de go in #913 (zie de bevriezing hierboven).
