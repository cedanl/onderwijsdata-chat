### Een staafgrafiek van een ranglijst staat op waarde en tekent geen lege categorie (#894)
- Bij "welke sector is het grootst" staat de grootste staaf nu bovenaan (of links), niet meer in de volgorde van de
  CBS-codes. Een categorie met waarde 0 of zonder waarde krijgt geen lege rij; de uitkomst van de grafiektool noemt
  welke categorieën zijn weggelaten, en ze staan wel in de data en de CSV-export.
- Categorieën met een eigen volgorde houden die: een tijdas, schooljaren, leeftijdsgroepen en getallen. Gegroepeerde
  staven (meerdere reeksen) blijven zoals ze waren.
