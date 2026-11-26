---
icon: lucide/flask-conical
---

# Test Environment Deployment

Test environment (`test.sdp.surf.nl`) is GitOps-managed via Flux and runs on every `main` push.

## Deployment Gate

**CI Job:** `kubernetes:verify-up` (runs on `main` push)
- Verifies: HelmRelease reconciliation succeeds
- Cluster: testing (SDP internal)
- Ingress: traefik-external, publiek via de allowlist `0.0.0.0/0`
- Replicas: 1 (`strategy: Recreate`, quotum)
- Resources: limits 900m CPU / 3Gi RAM, requests 500m / 512Mi (zie [Operatie](operatie.md#per-omgeving))

## Configuration

**Manifests:**
- `manifests/test/kustomization.yaml` — Flux patches
- `manifests/test/helmrelease.yaml` — HelmRelease CR
- `manifests/test/values.yaml` — Ingress + resources

**Secrets:**
- `manifests/test/secret.yaml` (SOPS-encrypted)

## Testaccounts en testgegevens

Afspraken voor de gedeelde testomgeving (#488, privacy H2):

- **Eigen account per tester en per auditspoor.** Gesprekken, rapporten, feedback en datarecepten zijn per
  gebruikersnaam gescheiden (`tests/test_account_isolatie.py` toetst dat op de API); wie een eigen account heeft, ziet
  alleen eigen werk en ruimt alleen eigen werk op. De beheerder voegt accounts toe aan `CHAT_USERS` in
  `manifests/test/secret_orig.yaml`, versleutelt met SOPS en pusht; Flux rolt de pod opnieuw uit (zie `Agents.md`,
  Secrets & Security). Het account `demo` blijft voor het team en voor demo's; metingen doe je niet op `demo`.
- **Tokenbudget op test.** Elk account heeft op test een ruimer budget dan de standaard: 6 mln per dag en 60 mln per
  maand in plaats van 1,5 en 15 mln (`TOKENBUDGET_DAG`, `TOKENBUDGET_MAAND` in `manifests/test/values.yaml`, #678, #1066).
  Het account `demo` is vrijgesteld (`TOKENBUDGET_VRIJGESTELD`, #1234): team, demo's en live audits delen het, en het
  zat tijdens audits aan zijn dagbudget. Zijn gebruik telt nog wel mee. Playground en productie houden de standaard,
  zonder vrijstelling.
- **Geen persoonsgegevens in de testomgeving**, ook geen dummy-BSN of fictief e-mailadres in een vraag: de vraag gaat
  naar de externe AI-dienst en wordt bewaard. De app waarschuwt bij een BSN, e-mailadres of telefoonnummer, maar
  blokkeert niet.
- **Opruimen na een ronde.** Elke tester verwijdert de eigen gesprekken en rapporten na afloop; de automatische
  opschoning (#485) haalt pas na 90 dagen (gesprekken, feedback) of 365 dagen (rapporten) weg wat niet meer is
  gebruikt. In `demo` verwijder je alleen wat je zelf maakte; bij twijfel laat je het staan, want een verwijderd
  gesprek van een ander is niet terug te halen.
- **"Verwijder al mijn gegevens" alleen op een eigen account** (#646). Op een eigen account ruimt die knop in de
  instellingen alles in één keer op (gesprekken, rapporten, dashboards, feedback en datarecepten). Gebruik hem nooit
  op `demo` of een ander gedeeld account: hij wist het werk van iedereen die dat account gebruikt, en dat is niet terug
  te halen.

## Isolatietest met twee accounts (#1235)

Twee gewone accounts, A en B, komen niet bij elkaars werk. Zes controles:

| # | Controle | Verwacht |
|---|---|---|
| 1 | B vraagt een gesprek of rapport (werkboek) van A op, of hernoemt het | 404, dezelfde body als bij een onbekend id |
| 2 | B vraagt het Word-document of de CSV van A op, of geeft feedback op het rapport van A | 404, dezelfde body als bij een onbekend id of een onbekende key |
| 3 | B bewaart een data-key van A in een eigen gesprek en heropent het | geen CSV (404), geen recept in zijn export, 0 data-keys in de chat |
| 4 | Gesprekken, zoekresultaten, werkboeken, gegeven feedback en de export van B | geen merkteken, id of naam van A |
| 5 | A doet "verwijder al mijn gegevens" | alles van B blijft precies zo |
| 6 | Zonder token, met onzin, met een vervalst of met een ingetrokken token | 401 op elk eindpunt hierboven; de chat sluit met 4001 |

**Lokaal en in CI.** `tests/test_account_isolatie.py` toetst alle zes op de app in het testproces, met twee accounts
in `CHAT_USERS`. Hij draait in de `pytest`-job van elke MR. Los draaien:

```bash
env UV_PYTHON=3.14 uv run pytest tests/test_account_isolatie.py tests/test_isolatietest_script.py -q
```

**Tegen een draaiende app.** `scripts/isolatietest.py` doet dezelfde controles over HTTP, met twee echte tokens. Hij
draait alleen tegen `localhost`, `127.0.0.1` of de testomgeving (`onderwijsdata-chat.test.sdp.surf.nl`, alleen via
https). Elke andere URL, ook playground en productie, weigert hij vóór het eerste verzoek (exitcode 2). `localhost` is
voor een app op je eigen machine: de wacht ziet niet waar een poort heen gaat, dus richt hem nooit op een port-forward
naar een gedeelde omgeving. Hij weigert ook `demo`, `gast` en twee keer hetzelfde account. Hij maakt alleen eigen
testgegevens met het merkteken `isolatietest-<run>` en ruimt die aan het eind op. Er gaat geen vraag naar het taalmodel: de test kost geen tokenbudget.

```bash
export ISOLATIE_URL=https://onderwijsdata-chat.test.sdp.surf.nl
export ISOLATIE_TOKEN_A=…        # token van het auditaccount
export ISOLATIE_TOKEN_B=…        # token van een tweede eigen account
export ISOLATIE_TOKEN_A_UIT=…    # optioneel: een tweede token van A; de test logt het uit (controle 6, ingetrokken)
uv run python scripts/isolatietest.py --data-key <key uit een gesprek van A> --verwijder-a
```

- Een token komt van `POST /api/auth/login` (account in `CHAT_USERS`) of, na een SRAM-login, uit de browser
  (`localStorage`, sleutel `edudata_token`). Een tweede token van A: log nog eens in, in een ander browserprofiel.
  Zet tokens alleen in de omgeving, niet als argument en niet in een issue.
- `--data-key` neemt een key uit een gesprek van A (de CSV-knop onder een antwoord of de export van A). Zonder vallen
  controle 2 (CSV) en 3 weg.
- `--verwijder-a` (controle 5) wist **alles** van account A en trekt al zijn tokens in. Alleen op het auditaccount,
  nooit op `demo` of een account van een tester.
- Per controle één regel `OK` of `FOUT`, dan het totaal; exitcode 0 als alles in orde is, 1 bij een fout. Zet die
  regels als uitkomst in het issue; ze bevatten geen token.

**Het auditaccount.** Eigenaar is de beheerder van de testomgeving (de eigenaar van dit project); hij maakt het aan en
heft het op. Beheer: een regel in `CHAT_USERS` in `manifests/test/secret_orig.yaml`, versleuteld met SOPS naar
`secret.yaml` (zie Testaccounts hierboven), of een tweede SRAM-profiel. Een agent maakt het niet aan en leest het
wachtwoord niet. Budget: hetzelfde als elk account op test, 6 mln per dag en 60 mln per maand (`TOKENBUDGET_DAG`,
`TOKENBUDGET_MAAND`); de isolatietest zelf verbruikt daar niets van. Account B is een tweede eigen account van de
beheerder, niet `demo`.

**Wat de test niet afdekt.** De datastore in het geheugen is gedeeld over alle gebruikers (`tools/store.py`, #13): hij
houdt open brondata (CBS, DUO, RIO), en dezelfde selectie geeft dezelfde key. Per gebruiker zijn het recept achter een
key, de data-keys van een gesprek en wat de CSV-export, het rapport en de foutmelding van een tool noemen; dat toetst
controle 3. Noemt iemand een key letterlijk in een vraag, dan leest een tool de open data achter die key, zoals hij ze
ook zelf zou laden.

## Rollout

```
git push origin main
  ↓
GitLab CI: build image + chart
  ↓
Flux watches manifests/test/ (polled every 1m)
  ↓
HelmRelease reconciles the new chart version (open range >=0.0.1-0.0)
  ↓
kubernetes:verify-up checks: pod ready within 5min
```

## Troubleshooting

If `kubernetes:verify-up` fails:

```bash
# Check Flux source reconciliation
flux get sources oci -n services-onderwijsdata-chat

# Check HelmRelease
kubectl get helmrelease -n services-onderwijsdata-chat

# Check pod status
kubectl get pods -n services-onderwijsdata-chat

# Logs
kubectl logs -n services-onderwijsdata-chat -l app.kubernetes.io/name=onderwijsdata-chat
```

## Relationship to Environments

- **Development** → volgt `main` zoals test (open range), maar is geen sport van de ladder: geen bereikbare URL
- **Test** → auto from `main` push (CI-verified)
- **Playground** → vaste release-pin, alleen via de promotie-MR (`docs/promoten.md`)
- **Production** → nog niet uitrolbaar (#674)
