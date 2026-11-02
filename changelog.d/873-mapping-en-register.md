### Herkomst van de UWV-sectorindeling en een register dat bijblijft (#873)
- Het instellingsregister (uit de DUO-bestanden) wordt na 24 uur opnieuw opgebouwd, zodat een nieuwe, gefuseerde of
  hernoemde instelling niet pas na een herstart bekend is. Laadt een DUO-bestand dan niet, dan blijft het vorige
  register staan, met een regel in het log, en volgt een uur later een nieuwe poging.
- Het manifest van de UWV-sectorindeling zegt nu ook dat de prompt onbekend is en dat de validatie openstaat; het
  refresh-script legt bij een volgende indeling model, prompt en een open validatie vast. Een steekproef van 30
  clusters (`docs/sector-cluster-steekproef.csv`) wacht op handmatige beoordeling.
- De 25 beroepenclusters die het taalmodel bij geen enkele sector zette, staan in `_niet_toegewezen`; een test
  bewaakt dat elk cluster van de UWV-snapshot een plaats heeft.
