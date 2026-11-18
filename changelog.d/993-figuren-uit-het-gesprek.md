### Rapport: de figuren uit het gesprek komen in het rapport, en alleen die (#993)
- Een figuur uit de chat kwam nooit in het rapport: het rapport tekende alles opnieuw, met hoogstens twee eigen
  grafieken. Een sankey die het model in de chat met een eigen script maakte, werd in het rapport een staafgrafiek.
- De checklist bij "Genereer rapport" noemt nu per vraag ook de figuren die op haar data rusten, met hun titel en
  standaard aan. Een figuur die een latere vraag tekende zonder nieuwe data ("maak hem horizontaal") staat bij de vraag
  van haar data. Een vraag uitzetten zet haar figuren uit; een figuur aanzetten zet haar vraag aan. Meer dan vier
  figuren kan niet; de dialoog zegt dat en houdt Genereer tegen.
- Het rapport toont precies de gekozen figuren (besluit 18-11): het rapportmodel tekent zelf geen grafiek of kaart
  meer. Zonder gekozen figuren heeft het rapport alleen tekst. De server maakt elke gekozen figuur opnieuw uit de stap
  die haar in de chat maakte (de grafiek- of kaartaanroep, of het script van de analyse) op de herstelde data, met
  dezelfde sandbox en controles als in de chat. De figuur-JSON van het opgeslagen gesprek wordt nooit gelezen. Het model
  krijgt de figuren als vaste beschrijving en schrijft er titel, toelichting en conclusie bij; hun waarden tellen als
  bewijs voor de controles, hun titels niet. De bronregel onder elke figuur en de periode in de titel blijven uit code.
- Lukt een figuur niet meer (data niet te herstellen, een fout in het script, een lege figuur), dan valt ze weg met de
  regel "Deze figuur uit het gesprek kon niet opnieuw gemaakt worden." en gaat het rapport door.
- Een figuur wordt niet meer bijgesneden tot een periode in haar titel: ze blijft zoals de gebruiker haar zag.
- De stap achter elke figuur wordt bewaard in het bewijs per antwoord (`beurtbewijs`, nieuwe kolom `figuren`, op
  SQLite en PostgreSQL vanzelf toegevoegd bij de start), zodat een heropend gesprek dezelfde figuren noemt. Ze gaat mee
  in de export van "Mijn gegevens" en weg met het gesprek. Een gesprek van vóór deze wijziging noemt geen figuren.
- Gemeten (#785): een rapport met de sankey van 13 stromen is 10 kB (de figuur zelf 7 kB), een rapport met vier
  figuren (die sankey en drie grafieken) 42 kB, ruim onder de grens van 4 MiB. De grens blijft.
