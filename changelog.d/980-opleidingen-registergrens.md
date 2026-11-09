### Dashboard Opleidingen: een instelling buiten het DUO-register heet niet meer "niet gevonden" (#980)
- De Studiekeuzedatabase kent 109 instellingen, het register van de dashboards (DUO) alleen de bekostigde: 54 ervan.
  Voor de rest, zoals Nyenrode en de Open Universiteit, zei het dashboard "niet gevonden in DUO-data", alsof er geen
  studiekeuzedata bestond. Nu staat er dat de instelling niet in het DUO-register staat waarop het dashboard steunt,
  dat de Studiekeuzedatabase er wel gegevens over heeft en dat je ernaar kunt vragen in de chat; ook op de galerijkaart.
- Elf instellingen die de Studiekeuzedatabase anders noemt dan DUO, zoals "Maastricht University" en "HAN University of
  Applied Sciences", worden nu ook onder die naam gevonden.
- `scripts/meet_skdb_dekking.py` meet apart hoeveel instellingen van de Studiekeuzedatabase in het register staan en
  hoeveel daarvan op hun eigen naam te vinden zijn.
