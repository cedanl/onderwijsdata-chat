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
