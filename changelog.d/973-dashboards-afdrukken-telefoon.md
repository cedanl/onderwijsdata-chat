### Dashboards: afdrukken, telefoon en minder verzoeken (#973)
- **Afdrukken:** een brede tabel (Opleidingen, 11 kolommen) werd op papier afgekapt; nu past hij in de breedte, met een
  kleinere letter, de kolomkoppen op elke pagina en geen rij over twee pagina's. De NSE-thema's (Opleidingen) en de
  definities van de kengetallen (Financiën) gaan bij het afdrukken open en daarna weer dicht.
- **Telefoon:** op 390 px scrolde Mijn instelling een paar pixels zijwaarts (tot 26 px): de tekst in de smalle
  kerncijfertegels paste niet. De regel onder het getal breekt nu af, "ten minste" mag boven het getal staan, en in een
  smalle tegel valt het decoratieve icoon weg.
- **Personeel:** een hogeschool of mbo-instelling vraagt `/api/dashboard/personeel` niet meer op en krijgt geen laadvlak;
  alleen een universiteit, of een instelling die de lijst niet kent (dan beslist de server).
