### Een regiovergelijking van mbo-instellingen noemt de nevenlocaties (#744)
- Een regionaal roc dat alleen een nevenlocatie in de regio heeft, viel weg uit een regiovergelijking: adressen en
  studentaantallen bestaan bij DUO alleen per instelling, met de plaats van de hoofdvestiging. Zone.college (hoofdvestiging
  Lochem) biedt 22 opleidingen aan in Doetinchem en kwam daardoor niet voor in een vergelijking van instellingen in
  Doetinchem. Zone.college is geen vestiging van het Graafschap College.
- De definitie van `PROVINCIE INSTELLING`, het instellingsprofiel van een mbo-instelling en de systeemprompt zeggen nu dat het
  adres de hoofdvestiging is, dat `mbo_opleidingsaanbod` de plaats per onderwijslocatie kent (`PLAATSNAAM`), en dat het
  antwoord moet melden dat studentaantallen per instelling gelden en niet per locatie.
- Nog niet gebouwd: de instellingen met een locatie in de regio koppelen aan hun studentaantallen. Het aanbod kent geen
  BRIN; die koppeling hoort bij het BRIN-register (#728).
