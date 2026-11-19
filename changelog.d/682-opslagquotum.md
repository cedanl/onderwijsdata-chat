### Opslagquotum per gebruiker (#682, S24)
- Per gebruiker bewaart de server hoogstens 1000 gesprekken en 500 rapporten en dashboards, samen hoogstens 100 MB
  (`MAX_GESPREKKEN_PER_GEBRUIKER`, `MAX_WERKBOEKEN_PER_GEBRUIKER`, `MAX_OPSLAG_PER_GEBRUIKER_MB`; `0` zet een grens uit).
- Daarboven wordt een nieuw gesprek of rapport niet bewaard, en zegt de app dat de opslag vol is: verwijder oude
  gesprekken of rapporten en probeer het opnieuw. Wat er al staat, blijft; een bestaand gesprek bijwerken mag.
