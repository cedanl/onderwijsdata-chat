### "Vaste maat" onder een antwoord dat alleen op get_maat rust (#1242)
- Een antwoord waarvan elke datastap een `get_maat` op één maat was, krijgt onder de tekst "Vaste maat: <naam>". De
  uitklap noemt de teldefinitie en waar en wanneer het recept is vastgelegd (issue en datum, nu een verplicht veld van
  elk recept in `MATEN`). Code zet het label uit de stappen van de beurt, nooit uit de modeltekst; een andere datastap
  (query_data, run_analysis, koppel_data, een lader), twee maten of een vast antwoord uit code geven geen label. Het
  label zegt welke vaste route het getal gaf, niet dat het gecontroleerd is.
- Het label staat in de gespreksexport en blijft bij het heropenen van een gesprek.
