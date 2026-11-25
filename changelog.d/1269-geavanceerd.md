### Instelling "Geavanceerd" (#1269)
- In Instellingen staat de schakelaar "Geavanceerd", standaard uit. Aan toont hij ook de code per stap in de kaart
  "Redenering", de technische key bij een getal, "Download data als CSV" en "Download cijfers als CSV" (met "Vraag opnieuw
  stellen" na een mislukte download), de keuze "Code per stap" in de gespreksexport en de modelkiezer. Uit gaat elke
  vraag met het standaardmodel; met een login houdt de server zich daar zelf ook aan.
- Geavanceerd zet alleen iets erbij: controles, "Let op"-regels, de herkomst in woorden, de bronnen en de CSV onder een
  grafiek staan er altijd. Een test toetst dat op hetzelfde antwoord in beide standen.
- Met een login staat de keuze bij het account op de server (`GET`/`PUT /api/mijn-gegevens/geavanceerd`), dus op elk
  apparaat dezelfde; ze staat in de export van "mijn gegevens" en gaat weg met "Verwijder al mijn gegevens". Zonder login
  houdt de browser haar.
- De welkomstdialoog vraagt "Wil je de code en de data achter een antwoord zien en zelf bijsturen?", met Nee als
  standaard. De nieuwe instelling `GEAVANCEERD_PILOT` zet Geavanceerd aan bij de eerste login van de genoemde accounts;
  daarna beslist de gebruiker. Rol, instelling of functie bepalen haar nooit.
