# Agents.md

Guidance for Claude and yourself when working on features in this repository.

Read `CLAUDE.md` first for full project context. This file focuses on repository management and feature workflow.

## Quick Reference

**Two repos, one codebase:**
- GitLab (private, canonical): alle ontwikkeling, CI en deploy (SDP).
- GitHub (public): automatische spiegel van GitLab `main` en alle tags. Job `sync:github` (stage `.post`) force-pusht `main` bij elke push naar `main` en de tag bij elke tag.

**Er wordt niets gecherry-pickt of gefilterd:** wat op GitLab `main` staat, staat ook op GitHub, inclusief `manifests/` en `.gitlab-ci.yml`. Dat is veilig omdat `secret.yaml` SOPS-versleuteld is en `.sops.yaml` alleen een publieke key bevat; plaintext (`secret_orig.yaml`) staat in `.gitignore`. Commit dus nooit een secret in leesbare vorm (zie "Secrets & Security").

**When you're working on a feature:**

| Wat | Waar | Naar GitHub |
|---|---|---|
| App-code, bugfix, feature, tests, docs | MR tegen GitLab `main` | vanzelf, via de spiegel |
| Kubernetes, SOPS, Docker, CI | MR tegen GitLab `main` | vanzelf; alleen versleutelde secrets |
| GitHub-release (notes) | `gh release create X.Y.Z --verify-tag` op de gespiegelde tag | handmatig, na de tag |

Werk op GitHub `main` nooit rechtstreeks: de volgende sync overschrijft het. PR's voor deze repo gaan via `glab` naar GitLab, niet via `gh` naar GitHub.

## Feature Development Workflow

Use **TDD + modularity** when building features (e.g., #37 toon _laatste_update):

1. **Test first**: Write failing test for the behavior you want
   ```python
   # tests/test_feature.py
   def test_feature_does_what_users_need():
       result = function_call()
       assert result has_expected_field
   ```

2. **Implement modularly**: Small, single-responsibility functions
   ```python
   # tools/catalog.py — extract helper
   def get_metadata_field(dataset_id: str) -> str | None: ...  # Clean, testable, reusable


   # tools/main.py — import & integrate
   from .catalog import get_metadata_field

   result["field"] = get_metadata_field(dataset_id)
   ```

   **Waar broncode hoort:** ophalen en de bronlogica (clients, kolommen, catalogus, bronversies) horen in `packages/`
   (`onderwijsdata`, `riodata`), het beleid (scope, poorten, etiketten, wat de gebruiker te zien krijgt) in `tools/`.
   Een pakket importeert de chat en het andere pakket nooit, en de chat gebruikt alleen de publieke API van een pakket
   (geen pad met underscore); `tests/test_importgrens.py` bewaakt dat en maakt de pipeline rood. De tests van een
   pakket staan in `packages/<naam>/tests` en draaien mee in de CI-job `pytest`.

   **Geen netwerk in tests:** uitgaand netwerk is dicht voor elke test zonder marker `live` (`tests/netwerkblok.py`,
   #915); een test die toch naar buiten gaat, faalt met de host erbij. Gebruik een bevroren fixture of mock
   (`tests/fixtures/`, `duo_fixtures`, `gouden`), of markeer de test `live` als hij echt een bron hoort te testen.
   Details in `CONTRIBUTING.md`.

3. **Verify tests pass**: `uv run pytest tests/test_feature.py -v`

4. **Commit once, with narrative**: Explain what & why
   ```
   feat(module): what changed and why it matters
   
   - Implementation detail
   - Why it's the right approach
   - References to design decisions (Arena AI review, etc)
   ```

## Before you commit

- **Houd app-code en ops-wijzigingen in aparte commits** (de hele geschiedenis staat openbaar op GitHub)
- **Example**: ✅ Good: commit 1 is "fix: update API endpoint", commit 2 is "chore: update k8s deployment"
- **Example**: ❌ Bad: single commit that changes API endpoint AND k8s config

Aparte, kleine commits houden de geschiedenis leesbaar en een revert eenvoudig.

## Deployment & versioning

**Ladder: test → playground** (development en production doen niet mee):

| Trigger | Environment | Mechanism |
|---|---|---|
| `git push origin main` | test | CI builds; Flux volgt de open range `>=0.0.1-0.0` |
| `git tag X.Y.Z` (bare, no `v`) | geen | publiceert alleen de chart + GitHub-spiegel |
| MR `chore/promote-playground` | playground | wijzigt de pin in `manifests/playground/helmrelease.yaml`; Flux installeert die versie |

**Een release in vijf stappen** (elke stap is een eigen beslissing; een tag deployt niets; volgorde en details in
`docs/promoten.md`):

0. **Voorbereiden** in de laatste MR naar `main`: `version` in `pyproject.toml` en `CITATION.cff`, de changelog met
   `scripts/changelog.py X.Y.Z`, `bron:ping`, `scripts/ijkwaarden.py`, `audit:python` en `audit:npm` groen of bewust
   geaccepteerd, en een recente `eval:bronwaarheid`-run met de uitslag in de MR (`docs/promoten.md`, stap 0).
1. **Test bekijken.** Merge naar `main`, wacht tot de pipeline van die commit groen is en kijk op test. Ontwikkel hier vrij; playground beweegt niet mee.
2. **Taggen** op precies die groene `main`-commit, kaal `X.Y.Z` (zonder `v`; SDP matcht `^[0-9]+\.`). Een volgende merge annuleert de vorige main-pipeline (auto_cancel), dus tag de commit die `origin/main` ná het wachten is. Zonder groene pipeline publiceert `version:promote` geen chart en faalt de promotie.
3. **Promoveren** via MR `chore/promote-playground` (auto-merge aan). Na de merge installeert Flux de pin binnen ~1 minuut.
4. **Vastleggen en verifiëren**: `mark` (marker start geen pipeline), `/version` en Flux-status controleren, daarna de GitHub-release maken.

```bash
git tag 2.2.0 <main-sha> && git push origin 2.2.0     # tag-pipeline publiceert chart; sync:github spiegelt de tag
uv run python scripts/promotie.py promote --version 2.2.0   # op branch chore/promote-playground; commit, MR
uv run python scripts/promotie.py mark                 # na merge: env/playground/<versie>
git push origin env/playground/2.2.0
gh release create 2.2.0 --verify-tag --latest --title "Release 2.2.0 — …" --notes-file notes.md   # release notes in het Nederlands
```

Verifiëren na de merge (`/version` is de bron van waarheid; `version` komt uit de chartversie = de tag, `commit` is de gebouwde commit):

```bash
kubectl --context playground get helmrelease onderwijsdata-chat -n services-onderwijsdata-chat \
  -o jsonpath='{.spec.chart.spec.version} -> {.status.history[0].chartVersion}'   # 2.2.0 -> 2.2.0
curl https://onderwijsdata-chat.playground.sdp.surf.nl/version
```

Let op:
- `/version` noemt `commit` kort (8 tekens) en per pakket onder `catalogus` de volledige commit waaruit `onderwijsdata` en
  `riodata` komen (de chat-commit, want ze staan in `packages/`; #888). De docker-build krijgt daarvoor de volledige
  `CI_COMMIT_SHA` als `GIT_COMMIT`. Snippets installeren de pakketten met `git+<GitHub-spiegel>@<die commit>#subdirectory=packages/<pakket>`;
  alleen een commit op `main` bestaat op de spiegel, dus een snippet uit een MR-build is niet installeerbaar.
- Playground nooit terug op een range zetten en nooit pinnen op `2.0.0` (die tag heeft geen chart).
- Alle tags zijn protected in GitLab (`*`): een verkeerde tag is niet te verwijderen zonder de bescherming op te heffen. Controleer de naam vóór het pushen.
- Release-notes beschrijven alles sinds de laatste GitHub-release; sla je een tag over (zoals 2.1.0), neem die wijzigingen dan mee.
- `promotie.py` heeft alleen PyYAML nodig; zonder Python 3.14 lokaal: `uv run --no-project --python python3 --with pyyaml python scripts/promotie.py …`.

Procedure: `docs/promoten.md`. CI-poort `env:promotion-ladder` bewaakt de pin.

See `manifests/README.md` and `docs/test-environment.md` for details.

**When you're done:**
- For bugfixes/features: Push to `main` → test volgt vanzelf; playground blijft staan tot een promotie
- For release: prepare the last MR (version, changelog, eval), see test, tag `X.Y.Z` on the green `main` commit, promote playground via MR, `mark`, verify `/version`, GitHub release (`docs/promoten.md`)

## Harbor-onderhoud

Image en chart staan in Harbor-project `ceda-onderwijsdata-chat` op `cr.surf.nl` (quotum 100 GiB). Elke pipeline,
ook elke MR-pipeline, pusht een image van ~350 MB. Het SDP-retentiebeleid bewaart elk image 31 dagen, omdat de scan
vlak na de push als pull telt. Zonder onderhoud loopt het quotum dus vol en faalt `docker:docker-build` met
`will exceed the configured upper limit of 100.0 GiB`. Handmatig opruimen in de UI heeft op 02-11 release 2.5.0
weggehaald terwijl playground die pinde, met een uitval van playground tot gevolg.

**Twee doelen:** het quotum blijft onder 80 %, en een image of chart die een omgeving gebruikt gaat nooit weg.

Regels:
- **Verwijder nooit met de hand**, niet in de Harbor-UI en niet met `harbor artifact delete`. Opruimen gaat alleen
  met `scripts/harbor_onderhoud.py`. Dat script herleidt per omgeving wat Flux volgt (de pin, of de hoogste chart
  binnen de range) en het image daarachter, en verwijdert niets als het een omgeving niet kan herleiden.
- **Draai het op een checkout van `origin/main`**: de pins komen uit `manifests/<env>/helmrelease.yaml`.
- **Eerst de dry-run lezen**, dan pas `--uitvoeren`. Klopt de regel "Omgevingen" niet met `/version` van test en
  playground, dan niet uitvoeren.
- **Release-tags (`X.Y.Z`) zijn immutable** via een regel in Harbor (*Policy → Tag Immutability*, repositories
  matching `**`, tags matching het patroon hieronder). Een immutable artifact is ook niet met de hand te verwijderen.
  Gebruik geen `*` in het patroon: `[0-9]*.[0-9]*.[0-9]*` matcht ook `2.5.4-rc.…` en `0.0.1-build.…`, en dan kan het
  script geen enkele build meer opruimen. Zet de regel nooit uit zonder besluit van de gebruiker; oude releases
  opruimen is zo'n besluit.

  ```text
  {[0-9],[0-9][0-9],[0-9][0-9][0-9]}.{[0-9],[0-9][0-9],[0-9][0-9][0-9]}.{[0-9],[0-9][0-9],[0-9][0-9][0-9]}
  ```
- **Laat het SDP-retentiebeleid staan.** Het script werkt ernaast. Het beleid aanpassen is een vraag aan SDP.
- **Rode `docker:docker-build` met "upper limit"** is geen codefout: `opruimen --uitvoeren`, daarna alleen die job
  opnieuw starten.

Wat blijft altijd staan: release-tags, `latest`, wat elke omgeving volgt, de 10 nieuwste main-builds (rollbackruimte
voor test), de 20 nieuwste MR-builds, alles van de laatste 24 uur en elke tag die het script niet herkent. Een chart
gaat alleen weg samen met zijn image.

```bash
python scripts/harbor_onderhoud.py status                 # quotum, omgevingen, immutability; exit 1 bij een probleem
python scripts/harbor_onderhoud.py opruimen               # dry-run
python scripts/harbor_onderhoud.py opruimen --uitvoeren   # echt verwijderen
```

**Toegang.** Lokaal via harbor-cli (`harbor login cr.surf.nl`) met robot `robot$ceda-onderwijsdata-chat+beheer`. De
gebruiker logt zelf in. Vraag of toon het secret nooit, en laat het nooit via `!` of een pipe in het gesprek lopen.
harbor-cli opent zonder `-o json` een interactief scherm; het script geeft dat altijd mee. Zonder PyYAML lokaal:
`uv run --no-project --python python3 --with pyyaml python scripts/harbor_onderhoud.py …`.

**Elke nacht** draait job `harbor:onderhoud` (schema op `main` met `HARBOR_ONDERHOUD=1`, `SAST_DISABLED=1` en
`SECRET_DETECTION_DISABLED=1`). Die doet `opruimen --uitvoeren` en daarna `status`, met robot
`robot$ceda-onderwijsdata-chat+ci-opruimen` uit de protected, masked variabelen `HARBOR_ROBOT_USER` en
`HARBOR_ROBOT_PASSWORD`. Een rode job betekent een fout in een omgeving, een quotum boven 80 % of een ontbrekende
immutability-regel; de log zegt welke.

Agents: draai `status` aan het begin van een sessie waarin je MR's maakt. Staat het quotum boven 70 %, draai dan
`opruimen` (dry-run, controleren, `--uitvoeren`) voordat je pusht.

## Geplande pakketjobs

De taken die in de oude pakketrepo's GitHub Actions waren, zijn GitLab-jobs met een eigen schema (#887):
`cbs:laatste-update` (`LAATSTE_UPDATE=1`, wekelijks), `catalogus:site` (`CATALOGUS_SITE=1`, dagelijks) en
`cbs:discovery` + `rio:broncontrole` (`BRONCONTROLE=1`, wekelijks). Schema's, instellen en de eerste handmatige run:
`docs/operatie.md`, "Bronpakketten bijhouden".

- Wijzigingen komen als MR van een branch `bot/<taak>` met auto-merge (`scripts/pakketbot.py`), nooit als push op
  `main`. Werk niet op een `bot/`-branch: de volgende run schrijft hem met force opnieuw. Een fix hoort in een eigen MR.
- Bevindingen staan in één open issue per controle (label `data`); het script werkt dat bij in plaats van elke week
  een nieuw te openen.
- Het token staat in de protected, masked variabele `PAKKETBOT_TOKEN`. Vraag of toon het nooit; de gebruiker maakt en
  vernieuwt het zelf.
- De catalogussites (`packages/*/docs`) staan op de Pages-site van de GitHub-mirror als `/catalogus/cbs/` en
  `/catalogus/rio/` (`.github/workflows/docs.yml`). Pas `docs/` daar niet met de hand aan.

## Git commands

```bash
# See what's on each remote
git log origin/main          # GitLab
git log github/main          # GitHub (spiegel; loopt een paar minuten achter op GitLab)

# Release tag (no 'v' prefix; deploys nothing by itself)
git tag 1.4.0
git push origin 1.4.0
```

## Worktrees

Parallel werken in een git worktree mag, maar ruim op:

- **Hergebruik** een bestaande worktree voor een volgend issue (`git switch -c <branch> origin/main`) in plaats van per issue een nieuwe te maken.
- **Verwijder** de worktree zodra de MR gemerged is: `git worktree remove <pad> && git worktree prune`.
- **`frontend/node_modules`** alleen installeren als je aan de frontend werkt (~350 MB per worktree).
- Zet geen projectlokale uv-cache (`cache-dir`, `UV_CACHE_DIR`) — met de gedeelde `~/.cache/uv` hardlinkt uv elke `.venv`, zodat een extra worktree vrijwel geen ruimte kost.

## Secrets & Security

### Core principle: nooit secrets via LLM

Secrets mogen NOOIT door een LLM-sessie gaan. Niet als input, niet als output,
niet als variabele, niet in commando's. Zodra een secret in een LLM-context
verschijnt, is het gecompromitteerd.

### Logs: geen gebruikerstekst op INFO+

Vraag, antwoord, toolargumenten en modeltekst komen op INFO en hoger alleen als lengte en hash in het log
(`core.logging_util.tekst_kenmerk`), de tekst zelf alleen op DEBUG (#475): het log valt buiten "gesprek verwijderen".

Hetzelfde geldt voor fouttekst en tracebacks, want die kunnen zulke tekst citeren (een httpx-fout citeert de
request-URL, een traceback uit de sandbox de modelcode): op INFO en hoger het type en een kenmerk
(`core.logging_util.foutkenmerk`, `fout_len=… fout_hash=…`), de tekst en de traceback alleen op DEBUG (#502). Geen
`exc_info` en geen `%s` met de uitzondering zelf op INFO+. Een interne fout houdt haar fout-ID: `log_interne_fout()`
zet ID, type en kenmerk op ERROR en de traceback onder hetzelfde ID op DEBUG. Een test in `tests/test_log_hardening.py`
houdt de productiecode hieraan; een bewuste uitzondering staat daar in `_BEWUST`, met de reden. Bewust wel leesbaar: de
`ConfigError`-regel in `server.py`, die alleen tekst uit `config.py` bevat.

### Rollen

| Rol | Doet WEL | Doet NIET |
|-----|----------|-----------|
| **LLM** | Infrastructuur code: values.yaml, config.py, Helm templates, app code | Secrets aanraken, kubectl met secrets, SOPS encryptie |
| **Developer** | secret_orig.yaml invullen, SOPS encryptie, kubectl apply, git commit | — |

### Workflow

1. LLM maakt infrastructuur-wijzigingen (values.yaml secretKeyRef, config.py, etc.)
2. Developer vult `secret_orig.yaml` lokaal in (buiten sessie)
3. Developer draait `sops encrypt --in-place secret.yaml` (buiten sessie)
4. Developer commit + push (buiten sessie)
5. Flux reconciled automatisch

### Bestanden

| Bestand | Inhoud | In git? |
|---------|--------|---------|
| `secret_orig.yaml` | Plaintext secrets (bron) | Nee (.gitignore) |
| `secret.yaml` | SOPS-versleuteld | Ja |
| `.sops.yaml` | SOPS creation rules + publieke key | Ja |

## Questions?

- **"Does this feature go to GitHub?"** → Ja, alles op GitLab `main` wordt gespiegeld; er is geen cherry-pick-stap
- **"I changed k8s and app code in one commit"** → Rebase before pushing; split into separate commits
- **"Can I sync GitHub → GitLab?"** → No; GitLab is source of truth. GitHub is a public mirror only.
