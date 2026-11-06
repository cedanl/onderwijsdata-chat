### Mijn instelling: de financiën van het bestuur en, op test, het personeel van de universiteit (#935, #936)
- Nieuwe kaart **Financiën van het bestuur** (mbo, hbo en wo): per verslagjaar solvabiliteit I en II, liquiditeit,
  rentabiliteit en rijksbijdragen van het bestuur van de instelling, naast het gewogen sectorcijfer van de Inspectie, met
  de signaleringswaarden als stippellijn en als signaal in woorden (geen oordeel) en de vaste voorbehouden: het cijfer
  geldt voor het hele bestuur en zegt niets over de kwaliteit van het onderwijs. Een sector die DUO anders toerekent en
  andere instellingen onder hetzelfde bestuur staan erbij. Geen ranking van besturen. Een instelling zonder bestuur in
  DUO's adressenbestand krijgt een nette melding; een lege waarde blijft leeg (geen 0).
- Nieuwe kaart **Personeel (wo)**, alleen waar `ENABLE_WO_PERSONEEL` aan staat (test): fte zonder GEZO per jaar uit WOPI,
  naar wetenschappelijk personeel en OBP en het aandeel tijdelijk, met de vaste zinnen (peildatum 31 december, fte is
  geen aantal personen, zonder GEZO). Een hogeschool of mbo-instelling krijgt geen kaart; een universiteit buiten WOPI de
  vaste melding.
- Nieuwe eindpunten `/api/dashboard/financien` en `/api/dashboard/personeel`. Ze geven 404 waar hun bron geen antwoord
  geeft, en de pagina vraagt ze dan niet op (`bronnen` uit `/api/config`). Een kaart die niet laadt, staat bovenaan als
  onderdeel dat niet laadde en breekt de rest van het dashboard niet. Het bronblok noemt de editie, de peildatum en bij de
  financiën de publicatiedatum.
- De kaarten rekenen met de functies van de chat-tools (`tools/financien.py`, `tools/wo_personeel.py`), zonder de
  aanwijzingen aan het model en zonder iets in de store te bewaren.
