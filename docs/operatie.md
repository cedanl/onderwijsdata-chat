# Operatie

Hoe de app op SDP draait en wat je doet bij een storing. Dit is de bron voor de werkelijke deploy; de releasestappen
staan in [Promoten naar playground](promoten.md), de tenant-aanvraag en de secrets in [Deployment](deployment.md).
Stand: release 2.5.0 (22-10-2026).

## Ladder

| Omgeving | Wat er draait | Hoe het beweegt |
|---|---|---|
| **test** | de laatste groene `main` | Flux volgt de open chartrange `>=0.0.1-0.0`; elke merge naar `main` rolt uit, `kubernetes:verify-up` controleert het |
| **playground** | een gepinde release (`manifests/playground/helmrelease.yaml`) | alleen via een MR `chore/promote-playground` (`docs/promoten.md`); de CI-poort `env:promotion-ladder` bewaakt de pin |
| **development** | — | doet niet mee aan de ladder |
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

**Eén pod, bewust.** De datastore (`tools/store.py`), de rate limiters en de SRAM-gebruikerscache leven in het
procesgeheugen; een tweede pod kent die niet (`tests/test_manifests.py` bewaakt `replicaCount: 1`). Gevolg: een deploy
of herstart is een korte onderbreking, en open chats krijgen "Verbinding verbroken". Het besluit over schaalbaarheid
staat in #677.

**Quotum.** Test en playground hebben `limits.cpu 1`, `requests.cpu 1`, `requests.memory 1Gi`, `limits.memory 4Gi` en
`limits.ephemeral-storage 5Gi`. Daarom `Recreate` (een tweede pod tijdens een rolling update past niet, #537) en 900m
voor de app, zodat de opschoonpod (100m) er nog bij past.

## Pod

- **Probes** (#675): `startupProbe` op `/health` (tot 150 s), `livenessProbe` op `/health` (5 s time-out, drie
  missers), `readinessProbe` op `/ready`: die toetst de database en of er een modelsleutel is, en geeft anders 503.
- **Stoppen**: `terminationGracePeriodSeconds: 60`; uvicorn geeft lopende HTTP-verzoeken 45 s. Een chat-WebSocket sluit
  uvicorn direct met code 1012; een lopend antwoord gaat bij een deploy verloren.
- **Bestandssysteem**: read-only, behalve een `emptyDir` op `/tmp` (werkmappen van `run_analysis`).
- **Image**: non-root `appuser`, base-images op digest, geen compiler of git in het runtime-image (#681).
- **Login** (#787): buiten `APP_ENV=local` start de app niet zonder login. Is `CHAT_USERS` in het secret leeg of ontbreekt `OIDC_PROVIDER`, dan stopt de pod bij het opstarten met een melding in het log (`start niet zonder login`) in plaats van stil als `gast` te draaien. Voor een bewust openbare demo zet je `ALLOW_ANONYMOUS=true`; het startlog geeft dan een WARNING. Een lege waarde komt voor na een rotatie van het secret: controleer `CHAT_USERS` vóór je uitrolt.
- **Logs**: JSON op elke SDP-omgeving (`APP_ENV`, #676); vraag- en antwoordtekst alleen als lengte en hash
  (`Agents.md`, "Logs").

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
| Geen data om een rapport of dashboard van te maken | de tekst van de `Gebruikersfout`, letterlijk | Opnieuw | niets: de gebruiker lost dit zelf op met een vraag |
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

`bron:ping` draait dagelijks op `main` (rond 07:15) en is rood als CBS, DUO, RIO of de kaart niet antwoordt
(`scripts/bronping.py`). Handmatig: `python scripts/bronping.py`.

## Onderhoud

- Een jaarlijkse review van deze pagina staat in [Promoten naar playground](promoten.md).
- Dependency-updates komen via Renovate (Dependency Dashboard, #656).
