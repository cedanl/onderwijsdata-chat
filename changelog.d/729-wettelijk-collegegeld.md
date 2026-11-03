### Het wettelijk collegegeld per studiejaar, uit de wettekst (#729)
- De chattool `get_collegegeld` geeft voor één studiejaar het wettelijk collegegeld: het bedrag voor voltijd en het
  minimum en maximum voor deeltijd en duaal (de instelling kiest het bedrag ertussen). De bedragen staan in een kleine
  vaste tabel in de code, nagelezen in artikel 9 van de Regeling financiën hoger onderwijs (BWBR0024005), voor
  2023/2024 tot en met 2027/2028. Het model kiest alleen het studiejaar en noemt geen bedrag uit zijn geheugen.
- Onder het antwoord staat "wetten.nl · Regeling financiën hoger onderwijs (BWBR0024005), artikel 9, versie van …,
  opgehaald op …", met een link naar dat artikel in die versie.
- Op een vraag naar het instellingscollegegeld zegt de app dat daarvoor geen open bron is, in plaats van een bedrag.
- Rond 1 september wordt de tabel nagelezen tegen de wettekst (docs/promoten.md, "Jaarlijks"); `bron:ping` wordt rood
  zodra het lopende studiejaar ontbreekt.
