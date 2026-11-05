# SDP Deployment Guide

Complete deployment procedure voor onderwijsdata-chat op SDP tenant.

## Prerequisites

- GitLab repository: `surf-internal/npuls/ceda/onderwijsdata-chat`
- SDP tenant: `services-onderwijsdata-chat` namespace
- CloudNativePG PostgreSQL cluster
- SRAM OIDC credentials (SURF Research Access Management)
- Modelsleutel (Azure AI Foundry en/of Willma)
- age-key for SOPS encryption

## Deployment Stages

### 1. Tenant Provisioning (SDP Team)

Tenant moet aangevraagd worden via Backstage:
- Department: NPULS - CEDA
- Service phase: Pilot/PoC
- Sizing: S
- Components: PostgreSQL (CloudNativePG)
- Namespace: `services-onderwijsdata-chat`

Output: Flux config in `kubernetes-clusters` repository

### 2. Database

Het platform levert per tenant een PostgreSQL-database; de verbindings-URI staat in de secret `onderwijsdata-chat-app` (key `uri`) en wordt als `POSTGRES_URI` aan de app doorgegeven (zie `manifests/<omgeving>/values.yaml`).

De app maakt de tabellen zelf aan bij de start (`persistence/db.py`, `CREATE TABLE IF NOT EXISTS`). Er is geen handmatige stap nodig.

`scripts/db-init.sql` is alleen bedoeld voor een zelf beheerde PostgreSQL-server waar de database en de applicatiegebruiker nog niet bestaan.

### 3. Secrets Configuration

Secrets zijn SOPS-encrypted. Dit doet de developer, buiten een LLM-sessie (Agents.md, "Secrets & Security"). Per
omgeving, hier development:

```bash
cp manifests/development/secret.yaml.example manifests/development/secret_orig.yaml
# vul de waarden in secret_orig.yaml in met een editor (het bestand staat in .gitignore)
cp manifests/development/secret_orig.yaml manifests/development/secret.yaml
sops encrypt --in-place manifests/development/secret.yaml   # .sops.yaml matcht alleen secret.yaml
git add manifests/development/secret.yaml
```

De app leest uit de secret `onderwijsdata-chat-secrets` de sleutels die `manifests/<omgeving>/values.yaml` met
`secretKeyRef` noemt: overal `CHAT_SECRET`, `CHAT_USERS`, `WILLMA_API_KEY`, `AZURE_AI_API_KEY` en `AZURE_AI_API_BASE`;
op test en playground ook `OIDC_CLIENT_ID` en `OIDC_CLIENT_SECRET`, op test ook `LOG_HASH_SECRET`. `POSTGRES_URI`
komt uit de secret `onderwijsdata-chat-app` van het platform (zie hierboven).

### 4. GitLab CI/CD Variables

Set in GitLab project settings:

- `SOPS_AGE_KEY` (Protected, Masked)
  - Decryption key for SOPS secrets
  - Generated: `age-keygen`

- `HARBOR_HOST` (Protected)
  - `cr.surf.nl`

- `HARBOR_PROJECT` (Protected)
  - `ceda-onderwijsdata-chat`

### 5. Release & Deploy

De volledige releaseprocedure staat in [Promoten naar playground](promoten.md); de ladder en het runbook in
[Operatie](operatie.md). Kort:

```bash
# GitLab is canoniek. Tag kaal, zonder v, op een groene main-commit:
git tag 2.5.0 <main-sha> && git push origin 2.5.0
# De tag-pipeline publiceert alleen de chart en spiegelt de tag naar GitHub; hij deployt niets.
uv run python scripts/promotie.py promote --version 2.5.0   # op chore/promote-playground, dan een MR
```

- **test** volgt elke merge naar `main` (open chartrange); `kubernetes:verify-up` controleert de uitrol.
- **playground** beweegt alleen via de promotie-MR die de pin in `manifests/playground/helmrelease.yaml` zet.
- **production** heeft geen CI-pad: `.gitlab-ci.yml` zet nergens `ENVIRONMENT_CLUSTER=production`, en de omgeving is
  nog niet uitrolbaar (#674).

## Verification

After deployment:

```bash
# Check Flux HelmRelease
kubectl get helmrelease -n services-onderwijsdata-chat

# Check Helm release status
helm list -n services-onderwijsdata-chat

# Check pod status
kubectl get pods -n services-onderwijsdata-chat

# Check ingress
kubectl get ingress -n services-onderwijsdata-chat

# Readiness (database en modelsleutel) en versie
curl https://onderwijsdata-chat.test.sdp.surf.nl/ready
curl https://onderwijsdata-chat.test.sdp.surf.nl/version

# Check logs
kubectl logs -n services-onderwijsdata-chat deploy/fn-onderwijsdata-chat --tail=100
```

## Troubleshooting

### HelmRelease not reconciling

```bash
# Check status
kubectl describe helmrelease onderwijsdata-chat -n services-onderwijsdata-chat

# Check Flux logs
kubectl logs -n flux-system deploy/helm-controller | grep onderwijsdata-chat

# Force reconciliation
kubectl annotate helmrelease onderwijsdata-chat \
  reconcile.fluxcd.io/requestedAt="$(date +%s)" \
  -n services-onderwijsdata-chat --overwrite
```

### Pod failing to start

```bash
# Check events
kubectl describe pod -n services-onderwijsdata-chat -l app.kubernetes.io/name=onderwijsdata-chat

# Check resource limits
kubectl top node
kubectl top pod -n services-onderwijsdata-chat

# Check secrets
kubectl get secret onderwijsdata-chat-secrets -n services-onderwijsdata-chat -o yaml
```

### Database connection issues

```bash
# Test connection from pod
kubectl exec -it <pod-name> -n services-onderwijsdata-chat -- \
  psql -U onderwijsdata_chat -d onderwijsdata_chat -h onderwijsdata-chat-rw

# Check network policy
kubectl get networkpolicy -n services-onderwijsdata-chat
```

## Environment-specific Notes

Alle omgevingen gebruiken `traefik-external` en draaien één pod zonder HPA; resources, quotum en toegang per
omgeving staan in [Operatie](operatie.md#per-omgeving).

## Maintenance

### Update dependencies

Renovate stelt dependency-updates voor als MR (Dependency Dashboard, #656). Met de hand:

```bash
uv lock --upgrade-package <pakket>          # Python
cd frontend && npm install <pakket>@<versie> # frontend
```

Daarna een gewone MR; een release volgt [Promoten naar playground](promoten.md).

Het bronpakket `onderwijsbronnen` (tot #910 `onderwijsdata` en `riodata`) heeft geen pin meer om te bumpen: het staat in `packages/` en een
wijziging daar gaat mee in dezelfde MR als de chatwijziging (#885). Wijzigt een pakket zijn afhankelijkheden, draai dan
`uv lock` en commit `uv.lock` mee.

### Backup PostgreSQL

Back-ups regelt het platform (SDP). Met de kubeconfig van het team zijn ze niet te zien: `kubectl get backups` en
`scheduledbackups` geven *Forbidden* in `services-onderwijsdata-chat`. Schema, retentie, hersteltest en RPO/RTO zijn
nog niet vastgelegd (#683).

```bash
# Handmatige dump, alleen als je bij de databasepod kunt (niet geverifieerd met de team-kubeconfig)
kubectl exec -it onderwijsdata-chat-rw-0 -n services-onderwijsdata-chat -- \
  pg_dump -U onderwijsdata_chat onderwijsdata_chat > backup.sql
```

## References

- [SDP Platform Documentation](https://git.ia.surf.nl/surf-internal/sdp/platform-documentation)
- [Flux CD Documentation](https://fluxcd.io/docs/)
- [CloudNativePG](https://cloudnative-pg.io/)
- [Helm Documentation](https://helm.sh/docs/)
