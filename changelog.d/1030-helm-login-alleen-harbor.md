### Helm-jobs loggen alleen nog in bij Harbor (#1030)
- `helm:lint`, `helm:publish` en `helm:promote` (SDP-componenten) logden na Harbor ook in op het GitLab-registry
  `git.sdp.surf.nl:5050`. Dit project heeft dat registry niet en gebruikt het nergens, maar de login liep vanaf de
  runners vaak in een time-out en maakte de jobs rood. `.gitlab-ci.yml` overschrijft nu `.helm_login` met alleen de
  Harbor-login.
