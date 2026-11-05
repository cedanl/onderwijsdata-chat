### Tests gaan niet meer stil het netwerk op (#915)
- De CI-pytest haalde UWV Open Match live op in `test_dashboard_arbeidsmarktmatch` en faalde op runners zonder route
  naar data.overheid.nl. De dashboardtests in `tests/test_instellingen.py` draaien nu op de fixture
  `arbeidsmarkt_fixtures`: de bevroren ROA-snapshot van de gouden tests en een UWV-frame met elk beroepencluster in
  elke provincie.
- Uitgaand netwerk is dicht voor elke test zonder marker `live`, in de chattests en in de pakkettests: een DNS-vraag
  of verbinding naar buiten faalt met de host erbij en "markeer de test als live of gebruik een fixture", ook als de
  code de fout opving en terugviel. Localhost en Unix-sockets blijven open. `tests/test_netwerkblok.py` bewaakt het.
- Met het blok aan vielen 33 tests op die stil DUO, CBS, UWV, ROA of RIO ophaalden: alle op fixtures of mocks gezet,
  geen enkele als `live` gemarkeerd. Het instellingsregister staat in unittests standaard leeg en vers klaar
  (`geen_registerdownload`); welke test het eerder live downloadde, hing af van de volgorde.
