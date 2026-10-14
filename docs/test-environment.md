# Test Environment Deployment

Test environment (`test.sdp.surf.nl`) is GitOps-managed via Flux and runs on every `main` push.

## Deployment Gate

**CI Job:** `kubernetes:verify-up` (runs on `main` push)
- Verifies: HelmRelease reconciliation succeeds
- Cluster: testing (SDP internal)
- Ingress: traefik-internal (SURF-only)
- Replicas: 1
- Resources: 200m CPU / 256Mi RAM

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
- **Opruimen na een ronde.** Elke tester verwijdert de eigen gesprekken en rapporten na afloop; er is nog geen
  automatische bewaartermijn (#485). In `demo` verwijder je alleen wat je zelf maakte; bij twijfel laat je het staan,
  want een verwijderd gesprek van een ander is niet terug te halen.

## Rollout

```
git push origin main
  ↓
GitLab CI: build image + chart
  ↓
Flux watches manifests/test/ (polled every 1m)
  ↓
HelmRelease reconciles image tag
  ↓
kubernetes:verify-up checks: pod ready within 5min
```

## Troubleshooting

If `kubernetes:verify-up` fails:

```bash
# Check Flux source reconciliation
flux get sources oci -n onderwijsdata-chat

# Check HelmRelease
kubectl get helmrelease -n onderwijsdata-chat

# Check pod status
kubectl get pods -n onderwijsdata-chat

# Logs
kubectl logs -n onderwijsdata-chat -l app=onderwijsdata-chat
```

## Relationship to Environments

- **Development** → manual; not in CI
- **Test** → auto from `main` push (CI-verified)
- **Playground** → auto from major tags (public)
- **Production** → auto from major tags (HPA-enabled)
