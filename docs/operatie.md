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

`bron:ping` draait wekelijks op `main` (maandag 07:15) en is rood als CBS, DUO, RIO of de kaart niet antwoordt
(`scripts/bronping.py`). Handmatig: `python scripts/bronping.py`.

## Onderhoud

- Een jaarlijkse review van deze pagina staat in [Promoten naar playground](promoten.md).
- Dependency-updates komen via Renovate (Dependency Dashboard, #656).
