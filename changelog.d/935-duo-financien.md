### Financiën per bestuur uit DUO's verantwoording uit XBRL (#935)
- Een nieuwe tool, `get_bestuursfinancien`, geeft de financiële positie van het bestuur van een mbo-, hbo- of
  wo-instelling: solvabiliteit I en II, liquiditeit, rentabiliteit en het totaal van de rijksbijdragen per verslagjaar,
  met de variant (standaard: geconsolideerd waar aangeleverd), het gewogen sectorcijfer van de Inspectie, de toets aan
  de signaleringswaarden van de Inspectie (2024) en vaste voorbehouden. De code rekent alles; het model niets.
- Bestuur 40833 blijft drie eenheden (ROC van Amsterdam, ROC van Flevoland, ROC TOP), nooit een som. Een wissel van
  variant, een bestuursfusie binnen de reeks (RIO) en een lege waarde (geen 0) krijgen een vaste melding. Besturen in
  po en vo staan er niet in.
- De bron staat in het pakket (`onderwijsbronnen` 0.10.0) als `onderwijsbronnen.duo.financien`, met de bestuurssleutel
  `onderwijsbronnen.Bestuurssleutel` en een catalogusrecord `duo:financien`. `bron:ping` bewaakt de nieuwste editie.
- Licentie: op de open onderwijsdata van DUO rust een CC0-verklaring, en dit bestand staat op diezelfde site. De tool
  geeft daarom ook op playground en productie cijfers (`LICENTIE_BEVESTIGD`).
