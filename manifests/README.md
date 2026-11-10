# Kubernetes Manifests — Flux + Kustomize

Flux-managed deployment configuration voor onderwijsdata-chat op SDP.

## Omgeving-specifieke configuratie

Elke omgeving draait **één pod** zonder HPA en zonder PDB, ook productie (ADR-011 in
[`docs/architecture-decisions.md`](../docs/architecture-decisions.md), besluit 09-11 op #677). Waarom: datastore,
gelijktijdigheidstellers en SRAM-cache leven in het geheugen van het proces (#421). Gevolg: elke uitrol is een korte
onderbreking, en die tellers beginnen na een herstart op nul (de tijdslimieten staan sinds #984 in Postgres). Opschalen is #984. Resources, quotum, probes,
het stoppen van de pod en het runbook staan in [`docs/operatie.md`](../docs/operatie.md); deze tabel is het overzicht.

| Omgeving | Ingress Class | Replicas | Limits (CPU / RAM) | Chartversie | URL |
|----------|---------------|----------|--------------------|-------------|-----|
| **development** | traefik-external | 1 | 500m / 1Gi | open range `>=0.0.1-0.0`, volgt `main` zoals test; geen sport van de ladder | `onderwijsdata-chat.dev.sdp.surf.nl` |
| **test** | traefik-external | 1 | 900m / 3Gi | open range `>=0.0.1-0.0`, volgt `main` | `onderwijsdata-chat.test.sdp.surf.nl` |
| **playground** | traefik-external | 1 | 900m / 2Gi | vaste release-pin via promotie-MR | `onderwijsdata-chat.playground.sdp.surf.nl` |
| **staging-otc** | traefik-external | 1 | 900m / 2Gi | vaste release-pin; **nog niet uitgerold** (#674) | `onderwijsdata-chat.staging.sdp.surf.nl` |
| **production-otc** | traefik-external | 1 | 900m / 2Gi | vaste release-pin; **nog niet uitgerold** (#674) | `onderwijsdata-chat.production.sdp.surf.nl` |
| ~~production~~ | traefik-external | 1 | 2000m / 4Gi | cluster `production` is op 2026-09-15 uitgezet; map vervalt (#674) | `onderwijsdata-chat.sdp.surf.nl` (resolvet niet) |

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
│   ├── helmrelease.yaml          # HelmRelease met de chartversie van deze omgeving
│   ├── helmrepo.yaml             # OCI registry (Harbor)
│   ├── kustomization.yaml        # Dev patches
│   ├── middleware.yaml           # Traefik-allowlist
│   ├── secret.yaml               # SOPS-versleutelde secrets (in git)
│   ├── secret.yaml.example       # sjabloon voor secret_orig.yaml (docs/deployment.md)
│   └── values.yaml               # Dev ingress (traefik-external)
├── test/
│   ├── helmrelease.yaml          # open range >=0.0.1-0.0
│   ├── helmrepo.yaml
│   ├── kustomization.yaml        # Test patches
│   ├── middleware.yaml
│   ├── secret.yaml               # SOPS-versleuteld (in git)
│   ├── secret.yaml.example
│   └── values.yaml               # Test ingress (traefik-external)
├── playground/
│   ├── helmrelease.yaml          # vaste release-pin (docs/promoten.md)
│   ├── helmrepo.yaml
│   ├── kustomization.yaml        # Playground patches
│   ├── middleware.yaml
│   ├── secret.yaml               # SOPS-versleuteld (in git)
│   ├── secret.yaml.example
│   └── values.yaml               # Playground ingress (traefik-external)
├── staging-otc/                  # OTC-cluster; production-otc is hetzelfde met host/doel `production`
│   ├── helmrelease.yaml          # vaste release-pin (zoals playground)
│   ├── helmrepo.yaml
│   ├── kustomization.yaml        # secret.yaml pas opnemen als de tenant bestaat (zie #674)
│   ├── secret.yaml.example       # sjabloon; secret.yaml volgt na de tenant (SOPS-sleutel van die tenant)
│   └── values.yaml               # APP_ENV=production, quotum als playground, opschonen aan
├── production-otc/               # idem
└── production/                   # vervallen (#674): cluster is uitgezet, map weg na het ladderbesluit
    ├── helmrelease.yaml
    ├── helmrepo.yaml
    ├── kustomization.yaml
    ├── middleware.yaml
    └── values.yaml
```

`staging-otc` en `production-otc` staan nog niet in `services/*-otc-cluster/kustomization.yaml` van
`kubernetes-clusters`: tot die registratie en de tenant (quotum, Postgres, minio-buckets, SRAM-registratie voor de
nieuwe host) er zijn, rolt er niets naartoe uit. Het pad dat de replacement-config van die clusters gebruikt is
`./manifests/staging-otc` resp. `./manifests/production-otc`.

## Ingress tiers

- **traefik-internal**: SURF-interne access; geen omgeving van deze app gebruikt dit nu (dev kreeg hiermee geen DNS-record)
- **traefik-external**: publiek DNS-record en toegang via de allowlist-middleware (dev/test/playground/production)

## Flux deployment

Flux reconcilet de HelmRelease per omgeving uit `main`; er is geen handmatige `kubectl apply`. Een wijziging gaat via
een MR, een release via de promotie-MR (`docs/promoten.md`). Production is niet uitrolbaar zolang #674 open is.

## Secrets management

Secrets zijn SOPS-versleuteld (`manifests/*/secret.yaml`). Flux ontsleutelt ze in het cluster met de age-key van de
tenant (`docs/operatie.md`). Een secret bewerken en versleutelen: `docs/deployment.md`, stap 3.

## Rollout strategie

1. **test** volgt elke push naar `main` op GitLab (open range `>=0.0.1-0.0`)
2. **playground** pint een release (`X.Y.Z`) en beweegt alleen via een
   `chore/promote-playground` MR, nadat je de wijziging op test hebt gezien
3. GitLab CI bouwt en publiceert het image/chart, en synct `main` en alle
   tags door naar GitHub als publieke spiegel
4. Flux volgt **chartversies** in Harbor (geen image-tags): een nieuwe chart binnen de range of de pin → reconciliatie
   in de betreffende environment
