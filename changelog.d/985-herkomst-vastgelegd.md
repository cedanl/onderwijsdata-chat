### De herkomst van een download blijft staan als de app een bron uit het geheugen haalt (#985)
- De CSV van een selectie, koppeling of berekening noemde haar bronnen alleen zolang die bronnen nog in het geheugen van
  de app stonden. Haalde de app een bron weg omdat het geheugen vol raakte, dan miste de kop die bron, met de hash, en
  bij een koppeling met de Studiekeuzedatabase de verplichte zin, versie en link van LCSK. De herkomst wordt nu
  vastgelegd op het moment dat de selectie of berekening ontstaat, en de kop blijft gelijk.
- Laadt de app een bron later opnieuw met een nieuwere stand, dan noemt de download van een eerdere berekening nog de
  stand waaruit die berekend is.
