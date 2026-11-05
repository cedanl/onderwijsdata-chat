### Arbeidsmarkt per ho-opleiding: ROA-subsector per regio en opleidingstype landelijk (#745)
- `get_roa_benchmark` heeft een optioneel argument `onderdeel`: het DUO-onderdeel van een hbo- of wo-opleiding. De tool
  geeft dan naast Bachelor en "Master, doctor" de gekoppelde ROA-subsector (of sector) voor de regio en de
  opleidingstypen eronder, die ROA alleen landelijk heeft. Een vraag als "sluiten de opleidingen van de RUG aan op de
  arbeidsmarkt in de regio" krijgt zo voor Gedrag en maatschappij de prognose van de master-subsector in Groningen en
  de landelijke cijfers voor psychologie, sociale wetenschappen en communicatie, in plaats van alleen het niveau.
- De koppeling van DUO-onderdeel naar ROA-categorie is een vaste tabel (`data/roa_koppeling.py`), gemeten op de
  ISCED-rubrieken van de erkende opleidingen in DUO. Wat niet eenduidig is, blijft ongekoppeld: Natuur,
  Sectoroverstijgend en de bachelors van Gedrag en maatschappij. Per niveau zegt het resultaat hoeveel opleidingen in
  een andere ROA-categorie vallen.
- De tool meldt zelf wat de bronnen niet kunnen: opleidingstype alleen landelijk, geen hbo/wo-splitsing bij ROA, en
  geen opleidingsniveau bij UWV-vacatures.
