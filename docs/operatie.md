# Operatie

Hoe de app op SDP draait en wat je doet bij een storing. Dit is de bron voor de werkelijke deploy; de releasestappen
staan in [Promoten naar playground](promoten.md), de tenant-aanvraag en de secrets in [Deployment](deployment.md).
Stand: release 2.5.0 (22-10-2026).

## Ladder

| Omgeving | Wat er draait | Hoe het beweegt |
|---|---|---|
| **test** | de laatste groene `main` | Flux volgt de open chartrange `>=0.0.1-0.0`; elke merge naar `main` rolt uit, `kubernetes:verify-up` controleert het |
| **playground** | een gepinde release (`manifests/playground/helmrelease.yaml`) | alleen via een MR `chore/promote-playground` (`docs/promoten.md`); de CI-poort `env:promotion-ladder` bewaakt de pin |
| **development** | de laatste `main`-build, zoals test | Flux volgt dezelfde open range `>=0.0.1-0.0`; geen sport van de ladder: geen bereikbare URL, niemand promoveert ernaartoe |
| **production** | — | **niet uitrolbaar**: geen secret, open chartrange, geen tenant en geen CI-pad (#674) |

Flux volgt **chartversies** in Harbor, geen image-tags. Een tag `X.Y.Z` (zonder `v`) publiceert alleen de chart en de
GitHub-spiegel; hij deployt niets.

## Per omgeving

Waarden uit `manifests/<omgeving>/values.yaml`, met de chart (`charts/onderwijsdata-chat/values.yaml`) als standaard.

| | test | playground | development | production |
|---|---|---|---|---|
| Replica's | 1 | 1 | 1 | 1 |
| Autoscaling (HPA) | uit | uit | uit | uit |
| Strategie | `Recreate` | `Recreate` | RollingUpdate | RollingUpdate (#674) |
| CPU limit / request | 900m / 500m | 900m / 500m | 500m / 200m | 2000m / 1000m |
| Geheugen limit / request | 3Gi / 512Mi | 2Gi / 512Mi | 1Gi / 256Mi | 4Gi / 1Gi |
| Ingress | `traefik-external` | `traefik-external` | `traefik-external` | `traefik-external` |
| Toegang | allowlist `0.0.0.0/0` (publiek) | publiek, geen middleware | allowlist `0.0.0.0/0` | allowlist `0.0.0.0/0` |
| Opschonen (CronJob) | aan | aan | uit | uit |
| `APP_ENV` | `test` | `playground` | `development` | `production` |

**Eén pod, bewust** (ADR-011, besluit 09-11 op #677). De datastore (`tools/store.py`), de limieten (login, berichten,
feedback, gelijktijdige verbindingen en runs) en de SRAM-gebruikerscache leven in het procesgeheugen; een tweede pod
kent die niet. De chart heeft daarom geen HPA en geen PDB, en `tests/test_manifests.py` bewaakt per omgeving één
replica. Wat dat betekent:

- **Elke uitrol of herstart is een onderbreking.** Bij `Recreate` (test, playground) is de app weg tot de nieuwe pod
  gestart is en de startupProbe haalt; op test duurde dat op 29-10 8 minuten (harde 503). Bij RollingUpdate
  (productie, als het quotum een tweede pod toelaat) blijft de app bereikbaar, maar open chats verliezen hun lopende
  antwoord en verbinden opnieuw.
- **Limieten tellen per proces.** Na een herstart begint iedereen weer op nul (login- en berichtlimiet).
- **Een node-drain of OOM is een storing voor iedereen**, tot Kubernetes de pod elders opnieuw heeft gestart.

Opschalen naar twee pods is de vervolgepic #984.

**Quotum.** Test en playground hebben `limits.cpu 1`, `requests.cpu 1`, `requests.memory 1Gi`, `limits.memory 4Gi` en
`limits.ephemeral-storage 5Gi`. Daarom `Recreate` (een tweede pod tijdens een rolling update past niet, #537) en 900m
voor de app, zodat de opschoonpod (100m) er nog bij past.

## Pod

- **Probes** (#675): `startupProbe` op `/health` (tot 150 s), `livenessProbe` op `/health` (5 s time-out, drie
  missers), `readinessProbe` op `/ready`: die toetst de database en of er een modelsleutel is, en geeft anders 503.
- **Stoppen** (#675, #677): eerst `preStop` (5 s `sleep`, zodat Traefik de pod loslaat voordat uvicorn stopt met
  luisteren), dan SIGTERM; uvicorn geeft lopende HTTP-verzoeken 45 s, binnen `terminationGracePeriodSeconds: 60`. Een
  chat-WebSocket sluit uvicorn direct met code 1012; een lopend antwoord gaat verloren en krijgt "Verbinding verbroken
  — antwoord onvolledig" met "Probeer opnieuw". Op 1012 zegt de voettekst "De app wordt bijgewerkt. De verbinding
  komt vanzelf terug." en blijft de frontend tot 12 minuten herverbinden (`HERSTART_MS` in
  `frontend/src/socketHealth.js`); daarna "Geen verbinding." met een knop.
- **Bestandssysteem**: read-only, behalve een `emptyDir` op `/tmp` (werkmappen van `run_analysis`).
- **Image**: non-root `appuser`, base-images op digest, geen compiler of git in het runtime-image (#681).
- **Login** (#787): buiten `APP_ENV=local` start de app niet zonder login. Is `CHAT_USERS` in het secret leeg of ontbreekt `OIDC_PROVIDER`, dan stopt de pod bij het opstarten met een melding in het log (`start niet zonder login`) in plaats van stil als `gast` te draaien. Voor een bewust openbare demo zet je `ALLOW_ANONYMOUS=true`; het startlog geeft dan een WARNING. Een lege waarde komt voor na een rotatie van het secret: controleer `CHAT_USERS` vóór je uitrolt.
- **Logs**: JSON op elke SDP-omgeving (`APP_ENV`, #676); vraag- en antwoordtekst alleen als lengte en hash
  (`Agents.md`, "Logs").

## Beschikbaarheid

Vastgesteld 09-11-2026 (ADR-011, #677). Deze tekst is publiek op de documentatiesite en is de input voor de afspraken
met Npuls en SURF AI Chat (#711). Hij staat niet in de app.

EDUdata draait als één serverproces. Dat houdt de dienst eenvoudig, maar je kunt het als gebruiker merken.

- **Beschikbaarheid: best effort.** We streven ernaar dat EDUdata bereikbaar is, maar er is geen afgesproken
  percentage en geen garantie. EDUdata is in de demofase.
- **Updates komen wanneer ze nodig zijn.** Er zijn geen vaste onderhoudsvensters. Tijdens een update is EDUdata even
  niet bereikbaar. Wat je dan ziet:
    - Een antwoord dat op dat moment wordt geschreven, breekt af met "Verbinding verbroken — antwoord onvolledig".
      Je gesprek en je rapporten blijven bewaard.
    - Onder het invoerveld staat "De app wordt bijgewerkt. De verbinding komt vanzelf terug." De app verbindt zelf
      opnieuw zodra de nieuwe versie draait; je hoeft de pagina niet te verversen.
    - Is de verbinding terug, dan stel je de afgebroken vraag opnieuw met "Probeer opnieuw".
    - Duurt het langer dan 12 minuten, dan staat er "Geen verbinding." met de knop "Opnieuw verbinden".
- **Bij een storing van de server** start het platform de server vanzelf opnieuw. Tot die weer draait, is EDUdata
  niet bereikbaar en zie je dezelfde meldingen als bij een update.
- **Hoe we reageren.** Een storing die we zelf merken of die aan ons wordt gemeld, pakken we zo snel als het kan op.
  Er is geen afgesproken reactie- of hersteltijd en geen bereikbaarheidsdienst buiten werktijd.

*Wat er gemeten is (de basis voor deze tekst):*

| | Gemeten |
|---|---|
| Duur van een uitrol met `Recreate` (test, 29-10) | 8 minuten harde 503 ("no available server"), daarna tot ± 18:25 wisselend de oude en de nieuwe frontend (vermoedelijk de oude shell uit de service worker, #670) |
| Uitrol met RollingUpdate (productie, als het quotum het toelaat) | niet gemeten; verwacht: geen 503, wel het verlies van lopende antwoorden |
| Hoe vaak test uitrolt | bij elke merge naar `main` |
| Hoe vaak playground uitrolt | alleen bij een promotie-MR (`docs/promoten.md`) |

Korter onderbreken kan met een snellere start of een kleinere pod. Zonder onderbreking kan het pas met twee pods
(#984).

## Secrets

SOPS-versleuteld in `manifests/<omgeving>/secret.yaml`; Flux ontsleutelt met de age-key van de tenant. Bewerken en
uitrollen: `Agents.md` (Secrets & Security) en de skill `sdp-secrets-management`. De platte versie
(`secret_orig.yaml`) staat in `.gitignore` en komt nooit in een commit of een LLM-sessie.

## Back-ups

De database is de Postgres van het platform (secret `onderwijsdata-chat-app`, key `uri`). Back-ups regelt SDP; met de
kubeconfig van het team zijn ze **niet te zien** (`backups` en `scheduledbackups` geven *Forbidden*). Schema, retentie,
hersteltest en RPO/RTO zijn nog niet vastgelegd: zie #683.

## Runbook

**Status bekijken**

```bash
curl https://onderwijsdata-chat.test.sdp.surf.nl/ready      # {"status":"ready",...} of 503
curl https://onderwijsdata-chat.test.sdp.surf.nl/version    # release en commit
kubectl --context testing get pods,helmrelease -n services-onderwijsdata-chat
kubectl --context testing describe pod -n services-onderwijsdata-chat -l app.kubernetes.io/name=onderwijsdata-chat
```

Voor playground `--context playground` en de playground-URL.

**Logs lezen**

```bash
kubectl --context testing logs -n services-onderwijsdata-chat deploy/fn-onderwijsdata-chat --tail=200
kubectl --context testing logs -n services-onderwijsdata-chat deploy/fn-onderwijsdata-chat --previous   # na een herstart
```

Een fout in de chat toont een fout-ID; zoek dat ID in het log voor type en kenmerk.

**Foutmeldingen: wat ziet de gebruiker, wat de beheerder** (#703)

| Categorie | De gebruiker ziet | Knoppen | De beheerder ziet |
|---|---|---|---|
| Limiet | vaste melding: even wachten | Opnieuw, en Opnieuw met een ander model | `Rate limit (poging n/4): provider=… status=…` van `agent.ratelimit`; kijk naar de status van de provider |
| API-sleutel ontbreekt of ongeldig, model onbekend, API onbereikbaar | "Het model is nu niet beschikbaar" met fout-ID; geen verwijzing naar `.env` | Opnieuw, en Opnieuw met een ander model | `Interne fout <ID> in model/API (<wat te controleren>): <type en kenmerk>` op ERROR: sleutel in het secret, `MODEL`/`AVAILABLE_MODELS` of `*_API_BASE` |
| Overige fout van model of API, time-out | "Fout bij het model of de API" met fout-ID | Opnieuw, en Opnieuw met een ander model | `Interne fout <ID> in model/API: <type en kenmerk>` op ERROR, de traceback op DEBUG |
| Fout in onze eigen code | "Er ging intern iets mis" met fout-ID en het verzoek het ID door te geven | alleen Opnieuw (een ander model helpt niet) | `Interne fout <ID> in verwerking: <type en kenmerk>` op ERROR, de traceback op DEBUG |
| Geen data om een rapport van te maken | de tekst van de `Gebruikersfout`, letterlijk | Opnieuw | niets: de gebruiker lost dit zelf op met een vraag |
| Verbinding weg tijdens een antwoord | "De verbinding viel weg voordat er een antwoord kwam. Stel je vraag opnieuw." | de vraag staat klaar om opnieuw te stellen | `VERBINDING`-regels met het verbindings-ID |

De gebruiker ziet nooit een uitzonderingstekst, bestandspad of traceback: alleen een `Gebruikersfout` (tekst voor de
gebruiker geschreven) komt letterlijk door, de rest krijgt een vaste melding. Is een vraag na een fout alsnog
beantwoord, dan blijft de melding als geschiedenis in het gesprek staan, maar zonder knoppen. De teksten staan in
`tests/e2e/fixtures/foutmeldingen.json`; `tests/test_foutmeldingen_vervolgstap.py` houdt dat bestand gelijk aan
`core/errors.py` en `tests/e2e/foutmeldingen.spec.js` toetst ze in de browser.

Tokengebruik: elke run logt `TOKENS  model=…  aanroepen=…  invoer=…  uitvoer=…  cache_gelezen=…  cache_geschreven=…`
(#678). Per gebruiker optellen gaat via het verbindings-ID: `VERBINDING open verbinding=<id> gebruiker=<pseudoniem>`.
Het pseudoniem staat er alleen met `LOG_HASH_SECRET`.

```bash
kubectl --context testing logs -n services-onderwijsdata-chat deploy/fn-onderwijsdata-chat --since=24h | grep TOKENS
```

**Herstarten**

```bash
kubectl --context testing rollout restart deploy/fn-onderwijsdata-chat -n services-onderwijsdata-chat
```

Nodig na een gewijzigd secret: Flux past het secret aan, maar de pod leest de variabelen alleen bij de start.

**Terugdraaien**

- *Playground*: zet in `manifests/playground/helmrelease.yaml` de vorige release terug, via dezelfde promotie-MR
  (`scripts/promotie.py promote --version <vorige>`). Nooit terug naar een range, nooit `2.0.0` (geen chart).
- *Test*: revert de commit op `main`; test volgt vanzelf.
- Een release met een schemawijziging (`persistence/db.py` migreert bij de start) heeft geen automatische terugweg.

**Pod start niet**

- `CreateContainerConfigError`: een key ontbreekt in het secret (`kubectl describe pod`).
- `Pending` met een quotumfout: een tweede pod past niet; controleer `strategy: Recreate` en de resources.
- `OOMKilled`: het geheugen van de pod is op (#546); `STORE_MAX_MB` moet onder de limiet blijven.
- Flux reconcilet niet: zie de skill `surf-kubectl-troubleshoot`; een stille stilstand diagnosticeer je met een
  server-side dry-run.

**Bron weg of gewijzigd**

Twee geplande jobs op `main` bewaken de bronnen, zonder LLM en zonder testomgeving. Een geplande pipeline bouwt en
rolt niets uit; welke job draait, bepaalt de variabele van het schema (CI/CD → Schedules).

| Job | Schema | Variabelen van het schema | Bewaakt | Signaal |
|---|---|---|---|---|
| `bron:ping` | dagelijks, rond 07:15 | `BRON_PING=1`, `SAST_DISABLED=1`, `SECRET_DETECTION_DISABLED=1` | bereikbaarheid en vorm van elke bron, plus de sweep | rood als een ping faalt; de sweep alleen als waarschuwing |
| `ijkwaarden:ververs` | maandelijks, bijv. de 1e om 07:45 | `IJKWAARDEN_VERVERS=1`, `SAST_DISABLED=1`, `SECRET_DETECTION_DISABLED=1` | de 23 ijkwaarden van de bronwaarheid-evals | geel bij een verschil (`allow_failure`) |

Zet in zo'n schema geen `EVAL_BASE_URL`: dan draait ook `eval:bronwaarheid`, met een modelaanroep per beurt. Beide
jobs zijn ook met de hand te starten via "Run pipeline" op `main` met dezelfde variabele.

*`bron:ping`* (`scripts/bronping.py --sweep`) doet eerst één echte aanroep per bron door de toollaag van de chat
(CBS, DUO, RIO, Inspectie, de DUO-indicatoren en de kaart-GeoJSON), en vraagt het lopende studiejaar op in de
tabel met het wettelijk collegegeld (#729; die ping leest geen bron, ze controleert dat de tabel bij is). De ping
`duo-instroom-mbo` legt de vaste bestanden van de mbo-eerstejaars en de ingeschrevenen per hoofdgroep in de dashboards
naast de lijst bij DUO en is rood zodra DUO een jaar publiceerde dat er niet in staat (#924, #934,
[Dashboards](dashboards.md)). Faalt er één, dan is de job rood en komt de
melding van de mislukte pipeline binnen. Daarna volgt de sweep over elke dataset die de chat kan opvragen
(`scripts/bronsweep.py`, #869), parallel en binnen een halve minuut (gemeten 02-11-2026: 13 s voor 226 controles):

- *CBS*: per tabel één `TableInfos`. `Modified … catalogus …: CBS werkte de tabel bij` betekent dat de cijfers na de
  catalogusbuild zijn herzien of aangevuld; de chat meldt die datum al per aanroep, maar de catalogus (en
  `_laatste_update` in zoekresultaten) loopt achter tot `cbs:laatste-update` de CBS-catalogus in `onderwijsbronnen` bijwerkt. Een HTTP-status
  betekent dat de tabel weg of verhuisd is.
- *DUO*: per dataset de bestandenlijst en per CSV alleen de kopregel, naast de schema-snapshot van `onderwijsbronnen.duo`.
  `kolomdrift` noemt de ontbrekende en nieuwe kolommen; `nieuw bestand` en `staat niet meer bij DUO` betekenen dat DUO
  een bestand verving. Dan leest `onderwijsbronnen.duo` de codekolommen van dat bestand niet meer als tekst: een nieuwe snapshot in
  `onderwijsbronnen.duo` is nodig.
- *RIO*: per register één record.

Een afwijking in de sweep is informatie, geen fout van de code: de job blijft groen, de afwijkingen staan met `!` in
de log en alle bevindingen in het artefact `bronping-sweep.json` (90 dagen). Handmatig:
`python scripts/bronping.py` (alleen de pings) of `python scripts/bronping.py --sweep`.

*`ijkwaarden:ververs`* (`scripts/ijkwaarden.py`) haalt de ijkwaarden opnieuw uit de bronnen en toont elk verschil met
`tests/e2e/ijkwaarden.json`. Het schrijft niets terug. Bij een verschil staat er een aanwijzing in de log: open een
issue, en is het een herziening of nieuwe levering van de bron, leg de nieuwe stand dan vast met
`scripts/ijkwaarden.py --schrijf` in een MR (`tests/ijkwaarden/README.md`).

In het log van de app wijzen deze regels op een bron die hapert of verandert:

- `BRON_RETRY bron=… poging=… reden=…`: een tijdelijke fout (5xx, 429, verbinding) die de chat opnieuw probeerde
  (#867). Af en toe is normaal; veel achter elkaar betekent een storing bij de bron. Een blijvende fout gaat na twee
  herhalingen als bronfout naar de gebruiker.
- `DUO_ENCODING`: een DUO-bestand was geen UTF-8 en is als cp1252 gelezen (#868).
- `DUO_SCHEMA_DRIFT`: de kolommen van een geladen DUO-bestand wijken af van de snapshot; het model krijgt een
  waarschuwing bij het resultaat (#868).

**Bronpakketten bijhouden**

De geplande taken van het bronpakket `onderwijsbronnen` (`packages/`; tot #910 `onderwijsdata` en `riodata`) waren GitHub Actions in de oude
pakketrepo's. Sinds #887 zijn het GitLab-jobs op `main`, elk met een eigen schema (CI/CD → Schedules, branch `main`,
plus `SAST_DISABLED=1` en `SECRET_DETECTION_DISABLED=1`, zoals bij `bron:ping`). Tijden in UTC, zoals de oude Actions.

| Job | Schema | Variabele | Wat | Uitkomst |
|---|---|---|---|---|
| `cbs:laatste-update` | wekelijks, zondag 06:00 (`0 6 * * 0`) | `LAATSTE_UPDATE=1` | `_laatste_update` per CBS-tabel uit TableInfos, dan afleiding, TableInfos/perioden, `bouw_artefact.py` en de pakkettests | MR `bot/cbs-laatste-update` met auto-merge; geen MR zonder wijziging |
| `catalogus:site` | dagelijks, 05:30 (`30 5 * * *`) | `CATALOGUS_SITE=1` | de catalogussites in `packages/onderwijsbronnen/docs/{cbs,rio}` opnieuw uit de catalogus en de voorbeelden (`scripts/catalogussite.py`) | MR `bot/catalogus-site` met auto-merge |
| `cbs:discovery` en `rio:broncontrole` | wekelijks, maandag 05:17 (`17 5 * * 1`) | `BRONCONTROLE=1` | nieuwe CBS-tabellen onder onderwijsthema's; DUO CKAN en de RIO-spec tegen de catalogus | één open issue per controle; rood als een bron niet antwoordt |

*Bot-MR's.* De Actions pushten zelf op `main`. Hier maakt `scripts/pakketbot.py mr` een commit op een vaste
botbranch (elke run opnieuw vanaf de commit van de pipeline, met force), opent of hergebruikt de MR naar `main` en zet
auto-merge zodra de MR-pipeline loopt. De MR doorloopt dus de volle pipeline en heeft net als elke MR één goedkeuring
nodig (de approval rule uit gitlab-config). Blijft een bot-MR liggen, dan schrijft de volgende run hem opnieuw.

*Issues.* `cbs:discovery` en `rio:broncontrole` houden elk één open issue bij ("Discovery: nieuwe CBS-tabellen ter
review" en "Broncontrole: review nodig (DUO CKAN en RIO)", label `data`). Bestaat het al, dan blijft het ongemoeid
zolang de stand gelijk is; bij een andere stand wordt de beschrijving vervangen en komt de nieuwe stand als notitie.
Sluit het issue na de beoordeling; een volgende bevinding opent een nieuw. De broncontrole vergelijkt met het
manifest van de vorige geslaagde controle, dat in de GitLab-cache staat (sleutel `rio-bronmanifest`). Is die cache leeg
(eerste run, of een runner zonder gedeelde cache), dan legt de run de basis: de vergelijking met de catalogus werkt,
"gewijzigd sinds vorige keer" pas vanaf de volgende run. De log zegt het als dat zo is.

*Catalogussites.* De Pages-workflow van de GitHub-mirror (`.github/workflows/docs.yml`) kopieert na de MkDocs-build
`packages/onderwijsbronnen/docs/cbs` naar <https://cedanl.github.io/onderwijsdata-chat/catalogus/cbs/> en
`packages/onderwijsbronnen/docs/rio` naar <https://cedanl.github.io/onderwijsdata-chat/catalogus/rio/>. De oude sites
(cedanl.github.io/cbs-onderwijsdata en /rio-onderwijsdata) worden niet meer onderhouden: die repo's zijn
sinds 2026-11-05 gearchiveerd (#889) en hun README verwijst naar de nieuwe plek. De sites zelf hebben geen banner en geen
doorverwijzing.

*Eenmalig instellen* (Maintainer; nooit in de repo, nooit in een sessie):

1. Projecttoken: Settings → Access tokens → naam `pakketbot`, rol **Developer**, scopes **api** en
   **write_repository**, vervaldatum zo ver als mag (noteer die: het token verloopt en moet dan vernieuwd).
2. Settings → CI/CD → Variables: `PAKKETBOT_TOKEN` met het token, **Masked** (of Masked and hidden) en **Protected**.
   Zonder deze variabele faalt elke pakketjob in de eerste stap (`scripts/pakketbot.py controleer`) met een melding
   die dit noemt; een token zonder de juiste rol of scopes geeft daar "GitLab weigert het token".
3. CI/CD → Schedules: de drie schema's uit de tabel, elk op `main` met de eigen variabele plus `SAST_DISABLED=1` en
   `SECRET_DETECTION_DISABLED=1`. Zet er geen `EVAL_BASE_URL` in.
4. Eén keer met de hand: "Play" (▶) bij elk schema. Vergelijk met de laatste GitHub-run: `cbs:laatste-update` geeft een
   MR met de `_laatste_update`-wijzigingen sinds de catalogusrevisie in `packages/` (de oude repo had daarna nog twee
   zulke commits, 25-10 en 01-11); `cbs:discovery` dezelfde tabellen als cbs-onderwijsdata#35; `rio:broncontrole`
   dezelfde meldingen als het laatste issue in rio-onderwijsdata (#45), op de gewijzigd-meldingen na (lege cache).
5. Daarna pas de Actions in de oude repo's uitzetten (#889).

## Onderhoud

- Een jaarlijkse review van deze pagina staat in [Promoten naar playground](promoten.md).
- Dependency-updates komen via Renovate (Dependency Dashboard, #656).
