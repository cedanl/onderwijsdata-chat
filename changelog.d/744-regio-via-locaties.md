### Een regiovergelijking van mbo-instellingen kiest de instellingen via hun onderwijslocaties (#744, deel 2)
- Vergelijkt de chat mbo-instellingen in een plaats, gemeente of provincie (een filter op de regio van de instelling,
  met een resultaat per instelling), dan telt nu ook elke instelling mee met een onderwijslocatie in dat gebied.
  Zone.college (hoofdvestiging Lochem) staat zo in een vergelijking van de instellingen in Doetinchem, waar het 22
  opleidingen geeft. Het niveau volgt uit het filter, niet uit een vaste keuze.
- Een totaal over de instellingen heen blijft bij de hoofdvestiging, zoals voorheen: een instelling met één locatie in
  Gelderland telt daar niet met al haar studenten mee. De toolresponse zegt hoeveel instellingen zo buiten het totaal
  blijven.
- Een vaste regel onder het antwoord noemt wie alleen via een locatie meedoet, met de hoofdvestiging, en zegt dat hun
  studentaantallen per instelling gelden en niet per locatie. De regel komt uit code; de snippet herhaalt dezelfde
  selectie.
- De locaties komen uit het opleidingsaanbod per locatie (DUO's export van RIO), de koppeling aan de instelling uit RIO
  (nieuw in riodata: `onderwijsaanbieders`) en de gemeente en provincie van een plaats uit CBS. Een storing bij een van
  die bronnen breekt het antwoord niet: dan alleen de instellingen met hun hoofdvestiging in het gebied.
- Nog niet: een arbeidsmarktregio als filter (geen mbo-bestand heeft er een kolom voor) en de peers van het dashboard
  "mijn instelling" (#904).
