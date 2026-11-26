### "Bewijs (JSON)" bij elk dataantwoord (#1244)
- Naast de CSV-knoppen staat "Bewijs (JSON)": één bestand met wat het antwoord al over zijn herkomst weet, met
  `schema: "onderwijsdata-chat/bewijs/1"` en de sleutels `manifest`, `bronnen`, `bronlinks`, `citaties`, `controle`,
  `controles` (wat de controle deed, #1260), `toolstappen` (per geslaagde stap de tool, haar argumenten en de code;
  nooit de ruwe uitvoer), `vaste_maat` en `antwoord`. Een sleutel die niet van toepassing is, is `null`. De browser
  bouwt het bestand uit het bericht: geen nieuwe API-route en geen modelaanroep. Een vast antwoord uit code zonder
  bronnen heeft de knop niet.
- De argumenten van elke toolstap gaan nu mee met het bewaarde gesprek, zodat een heropend gesprek hetzelfde bestand
  geeft. De bestandsnaam volgt de regel van de gespreksexport (#478): geen BSN, e-mailadres of telefoonnummer.
- Het blok Export onder een dataantwoord staat daardoor altijd op aanwezig: zonder tabel of geciteerd getal staat er
  alleen de bewijsknop, geen CSV.
