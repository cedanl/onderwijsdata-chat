### De geplande taken van de bronpakketten draaien in GitLab, en de catalogussites staan op de site van de chat (#887)
- De GitHub Actions van de oude pakketrepo's zijn GitLab-jobs met een eigen schema: `cbs:laatste-update` (wekelijks
  `_laatste_update` per CBS-tabel, met de hele keten tot en met de pakkettests), `catalogus:site` (dagelijks de
  catalogussites opnieuw uit de catalogus en de voorbeelden), `cbs:discovery` (nieuwe CBS-tabellen) en
  `rio:broncontrole` (DUO CKAN en de RIO-spec tegen de catalogus). Een geplande pipeline bouwt en rolt niets uit.
- Wat de Actions op `main` pushten, komt nu als MR van een `bot/`-branch met auto-merge (`scripts/pakketbot.py`): de
  wijziging doorloopt de volle pipeline en de goedkeuring. Een bevinding komt in één open issue per controle, dat
  alleen een notitie krijgt als de stand verandert, in plaats van elke week een nieuw issue.
- Het token staat in de protected, masked CI-variabele `PAKKETBOT_TOKEN`; zonder die variabele faalt de job meteen met
  een melding die zegt wat er moet gebeuren (`docs/operatie.md`, "Bronpakketten bijhouden").
- De catalogussites staan op <https://cedanl.github.io/onderwijsdata-chat/catalogus/cbs/> en
  `/catalogus/rio/`; de links in README en docs wijzen daarheen. De oude sites verwijzen door na #889.
- De oude workflows in `packages/*/.github/` (die GitHub in de monorepo nooit uitvoerde) zijn weg; hun tests staan nu
  in `tests/test_pakketjobs.py`. De RIO-site is opnieuw geëxporteerd: dezelfde gegevens, alleen een andere volgorde van
  de velden, zodat de eerste geplande run geen MR opent die alleen die volgorde wijzigt.
