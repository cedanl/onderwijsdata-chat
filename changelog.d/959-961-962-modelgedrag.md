### Chat: de code van de app bij een codeverzoek, eerst kiezen bij meer studies, koppelen zonder rijen te verliezen (#959, #961, #962)
- Vraagt de gebruiker om de code of een script om een uitkomst zelf na te rekenen, dan zet de app de code van de laatste
  datastap van het gesprek onder het antwoord, onder de kop **Code**: dezelfde code als onder "Bekijk code" bij die
  stap, met de juiste invoer (bijvoorbeeld `skdb.lees(*skdb.haal_op())` met de sleutel uit de omgeving). De chat schrijft
  geen eigen script meer met een verzonnen invoerbestand of kolomnamen. Een vraag naar een CROHO-, BRIN- of
  opleidingscode is geen codeverzoek.
- Vindt de Studiekeuzedatabase meer studies of instellingen bij een naam, dan zegt de melding vast dat de chat de keuze
  stelt en wacht. Haalt het antwoord toch studies op die de gebruiker niet koos, dan vangt een controle dat op en vraagt
  de chat eerst welke studie bedoeld is.
- Koppelen van twee bronnen: `relatie` geeft bij koppelkandidaten een vaste koppelregel mee, en de koppelzin van de
  Studiekeuzedatabase en de systeemprompt zeggen hetzelfde: eerst `relatie`, dan een left join vanuit de tabel van de
  vraag. Een rij zonder match blijft zichtbaar met een leeg veld en uitleg, nooit met 0, en verdwijnt niet door een
  inner join of `dropna`.
