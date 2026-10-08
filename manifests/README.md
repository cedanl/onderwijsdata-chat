# Kubernetes Manifests — Flux + Kustomize

Flux-managed deployment configuration voor onderwijsdata-chat op SDP.

## Omgeving-specifieke configuratie

| Omgeving | Ingress Class | Replicas | Resources | URL |
|----------|---------------|----------|-----------|-----|
| **development** | traefik-internal | 1 | 200m CPU / 256Mi RAM | `dev.sdp.surf.nl` |
| **test** | traefik-internal | 1 | 200m CPU / 256Mi RAM | `test.sdp.surf.nl` |
| **playground** | traefik-external | 2 | 500m CPU / 512Mi RAM | `playground.sdp.surf.nl` |
| **production** | traefik-external | 3–10 (HPA) | 1000m CPU / 1Gi RAM | `sdp.surf.nl` |

`playground` is the officially designated way of serving the app to end users
(vaste release-pin, door een promotie-MR; public, zie `docs/promoten.md`) — not `test`, which stays internal-only for CI
verification on every `main` push.

## Directorystructuur

```
manifests/
├── base/
│   ├── helmrelease.yaml          # Flux HelmRelease CR
│   ├── helmrepo.yaml             # OCI registry (Harbor)
│   ├── kustomization.yaml        # Kustomize base
│   ├── kustomizeconfig.yaml      # Kustomize nameReference config
│   └── values-base.yaml          # Shared defaults
├── development/
│   ├── kustomization.yaml        # Dev patches
│   ├── values.yaml               # Dev ingress (traefik-internal)
│   └── secret.yaml               # SOPS-encrypted secrets (niet in git)
├── test/
│   ├── kustomization.yaml        # Test patches
│   └── values.yaml               # Test ingress (traefik-internal)
├── playground/
│   ├── kustomization.yaml        # Playground patches
│   └── values.yaml               # Playground ingress (traefik-external)
└── production/
    ├── kustomization.yaml        # Production patches
    └── values.yaml               # Production ingress + HPA (traefik-external)
```

## Ingress tiers

- **traefik-internal**: SURF-interne access (dev/test)
- **traefik-external**: Public internet access (playground/production)

## Flux deployment

Flux reconciles HelmRelease per environment:

```bash
# Development
kustomize build manifests/development | kubectl apply -f -

# Production
kustomize build manifests/production | kubectl apply -f -
```

## Secrets management

Secrets zijn SOPS-encrypted (`manifests/*/secret.yaml`):

```bash
# Decryptie via Flux (SOPS_AGE_KEY env var in GitLab CI)
# Of handmatig:
sops -d manifests/development/secret.yaml | kubectl apply -f -
```

## Rollout strategie

1. **test** volgt elke push naar `main` op GitLab (open range `>=0.0.1-0.0`)
2. **playground** pint een release (`X.Y.Z`) en beweegt alleen via een
   `chore/promote-playground` MR, nadat je de wijziging op test hebt gezien
3. GitLab CI bouwt en publiceert het image/chart, en synct `main` en alle
   tags door naar GitHub als publieke spiegel
4. Flux detecteert nieuwe image tag → reconciliatie in de betreffende environment
