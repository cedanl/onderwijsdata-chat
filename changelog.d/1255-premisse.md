### Een vraag die een daling aanneemt terwijl de cijfers stijgen, krijgt dat te horen (#1255)
- "Waarom is het aantal studenten gedaald?" terwijl de reeks steeg: het antwoord opent met een vaste zin uit code,
  "De vraag gaat uit van een daling, maar het aantal ingeschrevenen steeg van 26.370 naar 28.355 (2021/22 →
  2024/25)." Beide getallen komen uit de opgehaalde reeks.
- Het model hoort vooraf dat de app de richting toetst en zoekt geen oorzaak voor een daling die er niet is.
- Bij twijfel (geen of twee richtingen, een ja/nee-vraag, een aandeel of percentage, een jaar dat de reeks niet heeft,
  geen verschil) blijft het antwoord zoals het was.
- Tien nieuwe evals: vijf vragen met een onjuiste en vijf met een juiste premisse op bevroren cijfers.
