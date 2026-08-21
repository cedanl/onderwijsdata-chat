# SDP Deployment Guide

Complete deployment procedure voor onderwijsdata-chat op SDP tenant.

## Prerequisites

- GitLab repository: `surf-internal/npuls/ceda/onderwijsdata-chat`
- SDP tenant: `services-onderwijsdata-chat` namespace
- CloudNativePG PostgreSQL cluster
- SURFconext OIDC credentials
- Anthropic API key
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

### 2. Database Initialization

Na tenant aanmaak, CloudNativePG cluster is ready:

```bash
# Connect to PostgreSQL pod in tenant namespace
kubectl exec -it onderwijsdata-chat-rw-0 -n services-onderwijsdata-chat -- psql

# Run init script
psql -U postgres -d onderwijsdata_chat < scripts/db-init.sql
```

### 3. Secrets Configuration

Secrets zijn SOPS-encrypted. Per environment:

```bash
# Development (example)
cat manifests/development/secret.yaml.example | sed \
  -e "s|<password>|$DB_PASSWORD|g" \
  -e "s|sk-ant-...|$ANTHROPIC_API_KEY|g" \
  > manifests/development/secret_orig.yaml

# Encrypt with SOPS
sops --encrypt manifests/development/secret_orig.yaml > manifests/development/secret.yaml

# Commit encrypted file (but not _orig)
git add manifests/development/secret.yaml
git rm manifests/development/secret_orig.yaml
```

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

Release workflow:

```bash
# On GitHub
git tag v0.1.0
git push origin v0.1.0

# GitHub Actions:
# 1. Pushes code + tag to GitLab
# 2. Triggers GitLab CI pipeline

# On GitLab:
# 1. Builds Docker image
# 2. Pushes to Harbor OCI registry
# 3. Packages Helm chart
# 4. Publishes to Harbor Helm repo
# 5. Flux reconciles new image tag

# Flux reconciliation (per environment):
# - development: always syncs latest main
# - test: syncs tag
# - staging: syncs tag (traefik-external)
# - production: syncs tag (traefik-external + HPA)
```

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

# Health check
curl https://onderwijsdata-chat.dev.sdp.surf.nl/health

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

### Development & Test
- `traefik-internal` ingress (SURF-only)
- 1 replica, minimal resources
- Good for testing and development

### Staging
- `traefik-external` ingress (public internet)
- 2 replicas, moderate resources
- Pre-production testing

### Production
- `traefik-external` ingress (public internet)
- 3–10 replicas with HPA
- High resource limits
- Enabled autoscaling

## Maintenance

### Update dependencies

```bash
# Python dependencies
uv update

# Frontend dependencies
cd frontend && npm update

# Commit and tag for release
git tag v0.2.0
git push origin v0.2.0
```

### Backup PostgreSQL

```bash
# CloudNativePG handles backups automatically
# Check backup status
kubectl get backups -n services-onderwijsdata-chat

# Manual dump (if needed)
kubectl exec -it onderwijsdata-chat-rw-0 -n services-onderwijsdata-chat -- \
  pg_dump -U onderwijsdata_chat onderwijsdata_chat > backup.sql
```

## References

- [SDP Platform Documentation](https://git.ia.surf.nl/surf-internal/sdp/platform-documentation)
- [Flux CD Documentation](https://fluxcd.io/docs/)
- [CloudNativePG](https://cloudnative-pg.io/)
- [Helm Documentation](https://helm.sh/docs/)
