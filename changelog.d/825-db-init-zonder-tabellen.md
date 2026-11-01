### `scripts/db-init.sql` maakt alleen gebruiker en database, met het wachtwoord als variabele (#825)
- Het script maakte ook de tabellen `conversations` en `workbooks`, in een verouderde vorm (zonder `laatst_gebruikt`
  en zonder de feedback-, recept- en intrekkingstabellen), en had een vast wachtwoord `change_me_in_production`. Nu
  maakt het alleen de gebruiker `onderwijsdata_chat`, de database en de rechten; de tabellen maakt de app bij de
  start. Het wachtwoord komt mee als psql-variabele: `psql -U postgres -v wachtwoord='…' -f scripts/db-init.sql`.
  Zonder die variabele maakt het script niets aan. Een tweede keer draaien slaat bestaande gebruiker en database
  over.
