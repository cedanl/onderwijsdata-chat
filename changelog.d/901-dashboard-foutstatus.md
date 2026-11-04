### Een dashboard zegt het als een bron niet laadde, biedt een nieuwe poging en toont geen verouderde data meer (#901)
- Ligt DUO eruit, dan meldt een dashboard dat de DUO-data nu niet beschikbaar is, met "Opnieuw proberen". Eerder las je
  "'X' niet gevonden in DUO-data … Pas de naam aan", alsof de instelling niet bestond. Een netwerk- of serverfout geeft
  ook een gewone zin met een nieuwe poging, niet meer "API 500" of "Failed to fetch".
- Een onderdeel dat niet laadde (de kaart, de sectorkamers, eerstejaars, gediplomeerden, de vacatures van UWV, de
  cijfers van ROA) staat bovenaan het dashboard met de reden, in plaats van stil weg te vallen.
- Op het arbeidsmarktdashboard en bij het diplomarendement van mijn instelling staat een laadvlak zolang die gegevens
  binnenkomen, en een melding met een nieuwe poging als ze niet kwamen. "Geen vacaturegegevens beschikbaar" staat er
  alleen nog als er echt geen vacatures zijn.
- Bij een onbekende naam noemt het dashboard de vijf namen die erop lijken, niet de eerste namen van het alfabet.
- De DUO-, UWV- en ROA-data van de dashboards en de adressen van de instellingen worden na 24 uur opnieuw opgehaald,
  zoals de rest van de app (#864, #873); eerder bleven ze tot een herstart van de server staan. Een mislukte of
  onvolledige lading wordt niet meer bewaard: de volgende poging haalt opnieuw op.
- Het laden van een dashboard heeft een tijdsgrens (90 s) en een limiet op wat er tegelijk laadt, zoals de chat
  (`DASHBOARD_TIMEOUT_S`, `MAX_DASHBOARD_LOADS`, `DASHBOARD_QUEUE_TIMEOUT_S`). Vragen meer dashboards tegelijk om
  dezelfde DUO-bestanden, dan worden die één keer opgehaald.
