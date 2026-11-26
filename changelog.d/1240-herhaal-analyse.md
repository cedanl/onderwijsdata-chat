### Herhaal deze analyse, met bron-diff voor CBS (#1240)
- Met de instelling "Geavanceerd" staat onder een antwoord met een CBS-tabel de knop "Herhaal deze analyse". De app haalt
  die tabellen opnieuw op bij CBS en zet de stand van nu naast die van toen: "Ongewijzigd", of bijvoorbeeld "Bron
  bijgewerkt op 15-06-2026; cijfer verschilt: 367.960 → 369.120 (…); versie van 14-04-2026 → 15-06-2026", met per stand
  de bijwerkdatum en de inhoudshash.
- Alleen getallen en bronversie, nooit de tekst van het antwoord; er wordt geen model aangeroepen. Het antwoord blijft
  staan, de data in de app ook, en de herhaling wordt niet bewaard.
- Het herhalen telt als chatbericht (berichtlimiet) en kan niet boven het tokenbudget. Alleen eigen antwoorden:
  `POST /api/conversations/{id}/antwoorden/{hash}/herhaal` geeft voor het antwoord van een ander hetzelfde 404 als voor
  een onbekend antwoord.
- Een prototype voor CBS; DUO en RIO volgen.
