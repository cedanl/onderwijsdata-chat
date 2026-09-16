# Agents.md

Guidance for Claude and yourself when working on features in this repository.

Read `CLAUDE.md` first for full project context. This file focuses on repository management and feature workflow.

## Quick Reference

**Two repos, one codebase:**
- GitLab (private): app + ops
- GitHub (public): app only

**When you're working on a feature:**

| Feature Type | Where to develop | How to sync | Push to |
|---|---|---|---|
| App code, bug fix, feature | GitLab `main` | Cherry-pick clean commits | both repos |
| Kubernetes, SOPS, Docker infra | GitLab `main` | (stays private) | GitLab only |
| Public docs, tests | GitLab `main` | Cherry-pick | both repos |

## Feature Development Workflow

Use **TDD + modularity** when building features (e.g., #37 toon _laatste_update):

1. **Test first**: Write failing test for the behavior you want
   ```python
   # tests/test_feature.py
   def test_feature_does_what_users_need():
       result = function_call()
       assert result has_expected_field
   ```

2. **Implement modularly**: Small, single-responsibility functions
   ```python
   # tools/catalog.py — extract helper
   def get_metadata_field(dataset_id: str) -> str | None:
       ...  # Clean, testable, reusable
   
   # tools/main.py — import & integrate
   from .catalog import get_metadata_field
   result["field"] = get_metadata_field(dataset_id)
   ```

3. **Verify tests pass**: `uv run pytest tests/test_feature.py -v`

4. **Commit once, with narrative**: Explain what & why
   ```
   feat(module): what changed and why it matters
   
   - Implementation detail
   - Why it's the right approach
   - References to design decisions (Arena AI review, etc)
   ```

## Before you commit

- **For public features**: keep app code separate from ops changes in different commits
- **Example**: ✅ Good: commit 1 is "fix: update API endpoint", commit 2 is "chore: update k8s deployment"
- **Example**: ❌ Bad: single commit that changes API endpoint AND k8s config

Clean commits mean cherry-picking to GitHub is trivial.

## Deployment & versioning

**The app promotes through environments based on tags:**

| Trigger | Where | Who pushes |
|---------|-------|-----------|
| `git push origin main` | development, test | CI (automatic) |
| `git tag vX.0.0` (major) | playground, production | Developer (manual) |
| `git push origin main` | GitHub (public mirror) | CI (automatic) |

See `manifests/README.md` for details.

**When you're done:**
- For bugfixes/features: Push to `main`, CI handles dev/test
- For release: Tag with `vX.0.0` when ready, CI handles playground/production

## Git commands

```bash
# See what's on each remote
git log origin/main          # GitLab
git log github/main          # GitHub (if synced)

# Tag for playground/production promotion
git tag v1.4.0
git push origin v1.4.0       # Triggers playground/prod deploy

# Cherry-pick a commit to GitHub
git checkout github/main
git cherry-pick <commit-hash>
git push github main

# After cherry-pick, update GitHub main
# (do this on GitHub side to avoid conflicts)
```

## Secrets & Security

### Core principle: nooit secrets via LLM

Secrets mogen NOOIT door een LLM-sessie gaan. Niet als input, niet als output,
niet als variabele, niet in commando's. Zodra een secret in een LLM-context
verschijnt, is het gecompromitteerd.

### Rollen

| Rol | Doet WEL | Doet NIET |
|-----|----------|-----------|
| **LLM** | Infrastructuur code: values.yaml, config.py, Helm templates, app code | Secrets aanraken, kubectl met secrets, SOPS encryptie |
| **Developer** | secret_orig.yaml invullen, SOPS encryptie, kubectl apply, git commit | — |

### Workflow

1. LLM maakt infrastructuur-wijzigingen (values.yaml secretKeyRef, config.py, etc.)
2. Developer vult `secret_orig.yaml` lokaal in (buiten sessie)
3. Developer draait `sops encrypt --in-place secret.yaml` (buiten sessie)
4. Developer commit + push (buiten sessie)
5. Flux reconciled automatisch

### Bestanden

| Bestand | Inhoud | In git? |
|---------|--------|---------|
| `secret_orig.yaml` | Plaintext secrets (bron) | Nee (.gitignore) |
| `secret.yaml` | SOPS-versleuteld | Ja |
| `.sops.yaml` | SOPS creation rules + publieke key | Ja |

## Questions?

- **"Does this feature go to GitHub?"** → Check `CLAUDE.md` "Што naar welke repo?" section
- **"I changed k8s and app code in one commit"** → Rebase before pushing; split into separate commits
- **"Can I sync GitHub → GitLab?"** → No; GitLab is source of truth. GitHub is a public mirror only.
