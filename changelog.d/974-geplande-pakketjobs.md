### Geplande pakketjobs werken weer op git.sdp.surf.nl (#974)
- De pakketbot (`catalogus:site`, `cbs:laatste-update`) kon zijn botbranch niet pushen: de runner zet zelf een
  credential helper met het job-token, git vroeg die eerst, en een job-token mag niet pushen. De push maakt de lijst
  met helpers nu eerst leeg, zodat alleen `PAKKETBOT_TOKEN` gebruikt wordt.
- `cbs:laatste-update` faalde op `tests/test_release.py`: de relatieve `UV_CACHE_DIR` van de geplande jobs kwam bij
  `uv build` in de pakketbron terecht en ging de sdist in. De cache staat nu absoluut onder `$CI_PROJECT_DIR`, net als
  bij `pytest`.
