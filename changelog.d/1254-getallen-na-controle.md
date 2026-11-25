### Getallen verschijnen pas na de controle (#1254)
- Tijdens het streamen staat elk getal dat de getalcontrole toetst (vier of meer cijfers, geen jaartal, of een
  percentage) als "…" in het antwoord, met de naam "getal wordt gecontroleerd" voor een schermlezer. Na de controle
  verschijnt het getal; een getal dat de controle intrekt, komt zo nooit in beeld. De "…" is even breed als het getal,
  dus de regel verspringt niet.
- Jaartallen, schooljaren en getallen onder 1.000 blijven zichtbaar tijdens het streamen.
- De regel komt van de server, bij elke `message_start` (`getalregel`): het scherm en de controle delen één regel.
- Nieuw nepscenario `mock/verzonnen` en een Playwright-test die bij elke delta controleert dat het ingetrokken getal
  nooit zichtbaar is.
