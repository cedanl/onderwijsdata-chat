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

- **Development** → doet niet mee aan de ladder
- **Test** → auto from `main` push (CI-verified)
- **Playground** → vaste release-pin, alleen via de promotie-MR (`docs/promoten.md`)
- **Production** → nog niet uitrolbaar (#674)
