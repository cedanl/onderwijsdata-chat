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
   def get_metadata_field(dataset_id: str) -> str | None: ...  # Clean, testable, reusable


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

**Ladder: test → playground** (development en production doen niet mee):

| Trigger | Environment | Mechanism |
|---|---|---|
| `git push origin main` | test | CI builds; Flux volgt de open range `>=0.0.1-0.0` |
| `git tag X.Y.Z` (bare, no `v`) | geen | publiceert alleen de chart + GitHub-spiegel |
| MR `chore/promote-playground` | playground | wijzigt de pin in `manifests/playground/helmrelease.yaml`; Flux installeert die versie |

**Een release in vier stappen** (elke stap is een eigen beslissing; een tag deployt niets):

1. **Test bekijken.** Merge naar `main`, wacht tot de pipeline van die commit groen is en kijk op test. Ontwikkel hier vrij; playground beweegt niet mee.
2. **Taggen** op precies die groene `main`-commit, kaal `X.Y.Z` (zonder `v`; SDP matcht `^[0-9]+\.`). Een volgende merge annuleert de vorige main-pipeline (auto_cancel), dus tag de commit die `origin/main` ná het wachten is. Zonder groene pipeline publiceert `version:promote` geen chart en faalt de promotie.
3. **Promoveren** via MR `chore/promote-playground` (auto-merge aan). Na de merge installeert Flux de pin binnen ~1 minuut.
4. **Vastleggen en verifiëren**: `mark` (marker start geen pipeline), `/version` en Flux-status controleren, daarna de GitHub-release maken.

```bash
git tag 2.2.0 <main-sha> && git push origin 2.2.0     # tag-pipeline publiceert chart; sync:github spiegelt de tag
uv run python scripts/promotie.py promote --version 2.2.0   # op branch chore/promote-playground; commit, MR
uv run python scripts/promotie.py mark                 # na merge: env/playground/<versie>
git push origin env/playground/2.2.0
gh release create 2.2.0 --verify-tag --latest --title "Release 2.2.0 — …" --notes-file notes.md   # release notes in het Nederlands
```

Verifiëren na de merge (`/version` is de bron van waarheid; `version` komt uit de chartversie = de tag, `commit` is de gebouwde commit):

```bash
kubectl --context playground get helmrelease onderwijsdata-chat -n services-onderwijsdata-chat \
  -o jsonpath='{.spec.chart.spec.version} -> {.status.history[0].chartVersion}'   # 2.2.0 -> 2.2.0
curl https://onderwijsdata-chat.playground.sdp.surf.nl/version
```

Let op:
- Playground nooit terug op een range zetten en nooit pinnen op `2.0.0` (die tag heeft geen chart).
- Alle tags zijn protected in GitLab (`*`): een verkeerde tag is niet te verwijderen zonder de bescherming op te heffen. Controleer de naam vóór het pushen.
- Release-notes beschrijven alles sinds de laatste GitHub-release; sla je een tag over (zoals 2.1.0), neem die wijzigingen dan mee.
- `promotie.py` heeft alleen PyYAML nodig; zonder Python 3.14 lokaal: `uv run --no-project --python python3 --with pyyaml python scripts/promotie.py …`.

Procedure: `docs/promoten.md`. CI-poort `env:promotion-ladder` bewaakt de pin.

See `manifests/README.md` and `docs/test-environment.md` for details.

**When you're done:**
- For bugfixes/features: Push to `main` → test volgt vanzelf; playground blijft staan tot een promotie
- For release: see test, tag `X.Y.Z` on the green `main` commit, promote playground via MR, `mark`, verify `/version`, GitHub release (`docs/promoten.md`)

## Git commands

```bash
# See what's on each remote
git log origin/main          # GitLab
git log github/main          # GitHub (if synced)

# Release tag (no 'v' prefix; deploys nothing by itself)
git tag 1.4.0
git push origin 1.4.0

# Cherry-pick a commit to GitHub
git checkout github/main
git cherry-pick <commit-hash>
git push github main

# After cherry-pick, update GitHub main
# (do this on GitHub side to avoid conflicts)
```

## Worktrees

Parallel werken in een git worktree mag, maar ruim op:

- **Hergebruik** een bestaande worktree voor een volgend issue (`git switch -c <branch> origin/main`) in plaats van per issue een nieuwe te maken.
- **Verwijder** de worktree zodra de MR gemerged is: `git worktree remove <pad> && git worktree prune`.
- **`frontend/node_modules`** alleen installeren als je aan de frontend werkt (~350 MB per worktree).
- Zet geen projectlokale uv-cache (`cache-dir`, `UV_CACHE_DIR`) — met de gedeelde `~/.cache/uv` hardlinkt uv elke `.venv`, zodat een extra worktree vrijwel geen ruimte kost.

## Secrets & Security

### Core principle: nooit secrets via LLM

Secrets mogen NOOIT door een LLM-sessie gaan. Niet als input, niet als output,
niet als variabele, niet in commando's. Zodra een secret in een LLM-context
verschijnt, is het gecompromitteerd.

### Logs: geen gebruikerstekst op INFO+

Vraag, antwoord, toolargumenten en modeltekst komen op INFO en hoger alleen als lengte en hash in het log
(`core.logging_util.tekst_kenmerk`), de tekst zelf alleen op DEBUG (#475): het log valt buiten "gesprek verwijderen".

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
