### Een herkende SRAM-instelling is het standaardprofiel; de onboarding opent zonder profiel (#777)
- De kop toonde de instelling uit je SRAM-account alsof hij actief was, maar de chat, de dashboards en de rapporten
  gebruikten hem niet. Nu werken ze allemaal met hetzelfde profiel (`frontend/src/profiel.js`): de instelling die je
  zelf koos, en zolang je niets koos de instelling die je SRAM-account opgeeft, als de app die kent. Een eigen keuze
  wint altijd, ook een bewust leeggemaakte; vroeger won in de kop juist SRAM van je keuze.
- Het welkomstvenster opent als er nog geen profiel is (geen instelling, gekozen of via SRAM, en geen functie), na
  het wachtwoordformulier en na de terugkeer uit SRAM gelijk. Een SRAM-gebruiker met een herkende instelling ziet het
  dus niet; een SRAM-gebruiker zonder herkende instelling nu wel, waar SRAM het vroeger nooit opende.
- Uitloggen wist het profiel nog steeds (gedeeld apparaat, besluit 30-10); er komt geen opslag op de server.
