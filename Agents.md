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

## Before you commit

- **For public features**: keep app code separate from ops changes in different commits
- **Example**: ✅ Good: commit 1 is "fix: update API endpoint", commit 2 is "chore: update k8s deployment"
- **Example**: ❌ Bad: single commit that changes API endpoint AND k8s config

Clean commits mean cherry-picking to GitHub is trivial.

## Git commands

```bash
# See what's on each remote
git log origin/main          # GitLab
git log github/main          # GitHub (if synced)

# Cherry-pick a commit to GitHub
git checkout github/main
git cherry-pick <commit-hash>
git push github main

# After cherry-pick, update GitHub main
# (do this on GitHub side to avoid conflicts)
```

## Questions?

- **"Does this feature go to GitHub?"** → Check `CLAUDE.md` "Што naar welke repo?" section
- **"I changed k8s and app code in one commit"** → Rebase before pushing; split into separate commits
- **"Can I sync GitHub → GitLab?"** → No; GitLab is source of truth. GitHub is a public mirror only.
