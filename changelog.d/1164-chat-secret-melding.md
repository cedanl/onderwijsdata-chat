### Een ontbrekende CHAT_SECRET stopt de start met een melding, niet met een traceback (#1164)
- Met `CHAT_USERS` of `OIDC_PROVIDER` en zonder `CHAT_SECRET` weigerde `core/auth.py` bij de import, en de start
  eindigde in een Python-traceback van ± 55 regels platte tekst, ook op `APP_ENV=test` waar het log JSON hoort te zijn.
  `Config.validate()` vangt die weigering nu op en meldt haar zoals de andere configuratiefouten: één logregel
  `Configuration validation failed: CHAT_SECRET moet ingesteld zijn …` (JSON buiten `APP_ENV=local`, leesbaar tekst
  lokaal), exit 1, geen traceback. Hetzelfde geldt voor een ongeldige `SESSION_TTL_HOURS` of `SESSION_MAX_HOURS`.
