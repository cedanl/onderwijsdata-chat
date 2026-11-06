### Collegegeld geciteerd, financiën binnen de grens, geen stille uitval (#970)
- De bedragen van het wettelijk collegegeld (voltijd, minimum en maximum voor deeltijd en duaal) krijgen een citatie
  met studiejaar, vorm en de wettekst als bron, ook in een antwoord dat andere data gebruikt; ze staan nu ook in de
  CSV-export van de citaties.
- De financiën van bestuur 40833 (ROC van Amsterdam, ROC van Flevoland en ROC TOP) passen weer binnen de grens van een
  toolresultaat (12.587 → 11.817 tekens op de editie 2021-2025): de methode van het sectorcijfer staat er één keer in,
  een jaar zonder signalering en een groep zonder jaren staan er niet als lege lijst in. De noot ("tel of middel ze
  nooit"), de voorbehouden en de data_key staan vooraan, zodat ze ook bij een langer resultaat niet wegvallen.
- Een storing bij RIO of DUO is geen stilte meer: een regiovergelijking via onderwijslocaties en een fusieregel (in een
  DUO-reeks en bij de financiën van een bestuur) krijgen een vaste regel welk deel niet is nagegaan en waarom. Faalt
  RIO voor één instelling, dan doen de andere nog mee.
- Haalt het model na "Meer instellingen passen" zelf een instelling op die de gebruiker niet koos, dan vangt de controle
  dat nu ook op, zoals bij studies. Is na drie keuzevragen geen keuzekaart meer mogelijk, dan stelt het model de keuze
  als vraag in het antwoord.
