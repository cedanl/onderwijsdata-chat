# Kubernetes Manifests — Flux + Kustomize

Flux-managed deployment configuration voor onderwijsdata-chat op SDP.

## Omgeving-specifieke configuratie

Elke omgeving draait **één pod** zonder HPA (staat in het geheugen, #421, #677). Resources, quotum, probes en het
runbook staan in [`docs/operatie.md`](../docs/operatie.md); deze tabel is het overzicht.

| Omgeving | Ingress Class | Replicas | Limits (CPU / RAM) | Chartversie | URL |
|----------|---------------|----------|--------------------|-------------|-----|
| **development** | traefik-external | 1 | 500m / 1Gi | open range, doet niet mee aan de ladder | `onderwijsdata-chat.dev.sdp.surf.nl` |
| **test** | traefik-external | 1 | 900m / 3Gi | open range `>=0.0.1-0.0`, volgt `main` | `onderwijsdata-chat.test.sdp.surf.nl` |
| **playground** | traefik-external | 1 | 900m / 2Gi | vaste release-pin via promotie-MR | `onderwijsdata-chat.playground.sdp.surf.nl` |
| **production** | traefik-external | 1 | 2000m / 4Gi | **niet uitrolbaar** (#674) | `onderwijsdata-chat.sdp.surf.nl` (resolvet niet) |

`playground` is de omgeving voor gebruikers (vaste release-pin, zie `docs/promoten.md`); `test` volgt elke push naar
`main` en is ook publiek bereikbaar (allowlist `0.0.0.0/0`).

## Directorystructuur

```
manifests/
├── base/
│   ├── helmrelease.yaml          # Flux HelmRelease CR
│   ├── helmrepo.yaml             # OCI registry (Harbor)
│   ├── kustomization.yaml        # Kustomize base
│   ├── kustomizeconfig.yaml      # Kustomize nameReference config
│   ├── network-policy.yaml       # Ingress-NetworkPolicy (egress staat live, nog niet in git: #674)
│   └── values-base.yaml          # Shared defaults
├── development/
│   ├── kustomization.yaml        # Dev patches
│   ├── values.yaml               # Dev ingress (traefik-external)
│   └── secret.yaml               # SOPS-encrypted secrets (niet in git)
├── test/
│   ├── kustomization.yaml        # Test patches
│   └── values.yaml               # Test ingress (traefik-external)
├── playground/
│   ├── kustomization.yaml        # Playground patches
│   └── values.yaml               # Playground ingress (traefik-external)
└── production/
    ├── kustomization.yaml        # Production patches
    └── values.yaml               # Production ingress (traefik-external); geen secret, zie #674
```

## Ingress tiers

- **traefik-internal**: SURF-interne access; geen omgeving van deze app gebruikt dit nu (dev kreeg hiermee geen DNS-record)
- **traefik-external**: publiek DNS-record en toegang via de allowlist-middleware (dev/test/playground/production)

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
4. Flux volgt **chartversies** in Harbor (geen image-tags): een nieuwe chart binnen de range of de pin → reconciliatie
   in de betreffende environment
