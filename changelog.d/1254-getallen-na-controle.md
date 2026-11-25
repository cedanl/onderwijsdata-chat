### Getallen verschijnen pas na de controle (#1254)
- Tijdens het streamen staat elk getal dat de getalcontrole toetst (vier of meer cijfers, geen jaartal, of een
  percentage) als "…" in het antwoord, met de naam "getal wordt gecontroleerd" voor een schermlezer. Na de controle
  verschijnt het getal; een getal dat de controle intrekt, komt zo nooit in beeld. De "…" is even breed als het getal,
  dus de regel verspringt niet.
- Jaartallen, schooljaren en getallen onder 1.000 blijven zichtbaar tijdens het streamen.
- Ook een getal dat nog binnenkomt ("27." en daarna "135", "70,6 pro" en daarna "cent") en een getal in de
  notatie van het model (9.5%, het Engelse 12,345) staan als "…" tot de controle klaar is.
- De kopieerknop kopieert zolang de getallen wachten de tekst zoals ze in beeld staat, met "…".
- De regel komt van de server, bij elke `message_start` (`getalregel`): het scherm en de controle delen één regel.
- Nieuw nepscenario `mock/verzonnen` en een Playwright-test die bij elke delta controleert dat het ingetrokken getal
  nooit zichtbaar is.
