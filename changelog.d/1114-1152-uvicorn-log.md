### Uvicorn-regels als JSON en geen toegangslog meer (#1152, #1114)
- Buiten `APP_ENV=local` zijn ook de start-, stop- en foutregels van uvicorn JSON, niet meer platte tekst tussen het
  JSON-log (een logaggregator kon die niet lezen). Een onafgevangen fout is één JSON-regel met de traceback in het
  veld `exception`. Lokaal blijft de leesbare tekstvorm.
- Het toegangslog van uvicorn is uit. Het schreef per verzoek het client-adres met poort en het volledige pad met
  gespreks- en werkboek-ID's, en koppelde zo een gesprek aan een bezoeker; de privacytekst ("Het logboek": alleen
  tijdstippen, toolnamen en het model naast lengte en hash) klopt nu weer.
