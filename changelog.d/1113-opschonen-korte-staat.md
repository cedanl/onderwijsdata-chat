### Opschonen: ook tokengebruik, intrekkingen en limietpogingen (#1113)
- `python -m persistence.opschonen` (de nachtelijke CronJob) ruimt nu ook `tokengebruik` ouder dan 62 dagen op, en
  verlopen rijen in `revoked_tokens`, `revoked_users` en `rate_limit_hits`. De samenvatting noemt hun aantallen en
  `--droog` telt ze met dezelfde voorwaarden zonder te verwijderen.
- Tot nu toe gebeurde dat alleen bij het starten van de app en bij uitloggen of intrekken: op een pod die weken niet
  herstart (playground pint een release) en waar niemand uitlogt, bleven rijen langer staan dan de 62 dagen uit de
  privacytekst (AVG art. 5 lid 1 sub e). De voorwaarden staan nu op één plek (`db.verlopen_staat`), voor de start en voor
  de nachtelijke taak.
