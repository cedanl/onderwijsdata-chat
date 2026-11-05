### Personeel van de universiteiten uit WOPI (UNL), alleen op test (#936)
- Nieuwe tool `get_wo_personeel`: personeel in dienst van een universiteit of van de 14 universiteiten samen, uit het
  WOPI-personeelsbestand van Universiteiten van Nederland, peildatum 31 december. Standaard in fte en zonder het
  HOOP-gebied Gezondheid; met GEZO alleen op uitdrukkelijk verzoek en nooit gemengd. Uitsplitsing naar
  wetenschappelijk personeel en OBP, functie, vast en tijdelijk, geslacht, en personen per leeftijdsklasse. Elk
  antwoord noemt de peildatum, de GEZO-variant en de vaste voorbehouden (fte is geen personen, wat niet meetelt);
  de bronregel is "WOPI {jaar}, Universiteiten van Nederland, peildatum 31-12-{jaar}, excl. sector Gezondheid".
- Een vraag naar personeel van een hogeschool of mbo-instelling krijgt een vaste melding dat er geen open bron is;
  de vier wo-instellingen die geen lid zijn van UNL krijgen er een zonder getal.
- Achter de vlag `ENABLE_WO_PERSONEEL`, die alleen op test aan staat: UNL moet nog schriftelijk bevestigen dat
  hergebruik mag. Playground en productie zien de tool niet.
- Pakket `onderwijsbronnen` 0.10.0: nieuwe bron `unl` (`unl.load`, `unl.lees`, `unl.haal_op`) die de records van de
  draaitabellen leest, niet de getoonde cellen; nieuwe dependency `defusedxml`. Het ID `unl:wopi` staat in het
  ID-contract, niet in `catalog(source="all")` en niet in de zoekcatalogus van de chat.
