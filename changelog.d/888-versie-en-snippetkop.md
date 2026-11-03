### Versie en installatieregel van de bronpakketten kloppen weer, zonder git-installatie (#888)
- Een snippet noemt in zijn kop de pakketversie, de appversie en de commit waaruit de app is gebouwd, en de
  installatieregel haalt de pakketten uit een subdirectory van de publieke GitHub-spiegel op die commit:
  `pip install "riodata @ git+https://github.com/cedanl/onderwijsdata-chat@<commit>#subdirectory=packages/riodata"`.
  Sinds #885 viel de kop terug op `pip install "riodata==0.7.0"`, en dat is niet installeerbaar: de pakketten staan niet
  op PyPI. Kent de omgeving haar commit niet (lokaal), dan zegt de kop dat en installeert de regel de nieuwste versie.
  Snippets van vóór de verhuizing blijven installeren zolang de oude pakketrepo's bestaan.
- `/version` noemt bij `onderwijsdata` en `riodata` weer een `commit`: de volledige chat-commit waaruit het pakket komt
  (`null` zonder build-arg). `commit` bovenaan blijft de korte vorm. De docker-build geeft daarvoor de volledige
  `CI_COMMIT_SHA` mee als `GIT_COMMIT`; de image-tag in de chart (`CI_COMMIT_SHORT_SHA`) verandert niet.
