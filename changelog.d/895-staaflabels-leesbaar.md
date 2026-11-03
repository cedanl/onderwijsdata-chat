### Volledige categorienamen en een waarde die niet meer scheef in een smalle staaf staat (#895)
- Het CBS kapt zelf de naam van veel categorieën af op circa 40 tekens ("04 Recht, administratie, handel en za…").
  De app zet nu de volledige naam terug uit de omschrijving die het CBS erbij geeft, in grafieken, tabellen en
  `get_cbs_dimension`. Een naam die niet bij de omschrijving past, blijft zoals het CBS hem geeft.
- In een staafgrafiek blijft een naam tot 60 tekens voluit; een langere naam wordt op een woordgrens afgekapt, met de
  volledige naam en de waarde in de hover. Twee namen die daardoor gelijk zouden worden, blijven voluit.
- Een korte staaf toont zijn waarde horizontaal, in de staaf als hij past en anders erachter, niet meer gedraaid.
