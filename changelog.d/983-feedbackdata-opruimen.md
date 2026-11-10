### De opgeslagen feedback per antwoord is weg (#983)
- De tabel `answer_feedback` met de oude oordelen (👍/👎, toelichting en de kopie van vraag, antwoord en stappen) gaat
  bij de start van de app weg (`DROP TABLE IF EXISTS`, op SQLite en PostgreSQL, bij elke start opnieuw en zonder fout
  als zij er al niet meer is).
- Exporteren, verwijderen en de nachtelijke opschoning slaan haar niet meer over of mee: de export heeft geen
  `answer_feedback` meer, "Verwijder al mijn gegevens" en het log noemen haar niet meer, en een verwijderd gesprek
  koppelt geen feedback meer los (#476).
- De privacytekst (app en `docs/privacy.md`), de verwijderdialoog en `SECURITY.md` zeggen dat een oordeel op een
  antwoord niet meer wordt bewaard. Het bewijs per antwoord (`beurtbewijs`) blijft.
