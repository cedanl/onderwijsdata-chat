### De privacytekst is op B1 en klopt met de code (#1139, #1140, #1144, #1119, #1184)
- De privacypagina en de popup zijn herschreven in korte, duidelijke zinnen: geen zin boven de 25 woorden (eerst 15 van
  de 66, de langste 51 woorden) en gemiddeld 12,6 woorden per zin. Elk kopje begint met één korte zin, zoals "Na 90
  dagen zonder gebruik verwijderen we een gesprek, na 365 dagen een rapport." Vaktaal als hash, OIDC-state, PKCE en
  toolstappen is weg of uitgelegd, en alle datums staan als "19 oktober 2026".
- "na90 dagen" is weer "na 90 dagen" (#1144), en de tekst noemt je rapporten in plaats van "werkboeken" en een
  dashboardchat die er niet meer is (#1140). De meldingen zeggen nu "Rapport is nog niet geladen" en "Rapport niet
  gevonden", en bij een Word-download van iets dat geen rapport is: "Dit is geen rapport, dus er is geen Word-document
  van te maken."
- De tekst zegt wat "Verwijder al mijn gegevens" laat staan: de tellers van het tokenbudget en de limieten staan onder
  een pseudoniem, zonder accountnaam, en gaan na hoogstens 62 dagen weg. Ook staat erin dat de app geen toegangslog
  schrijft (#1114).
- `docs/privacy.md` noemt de omgevingen waar de nachtelijke opschoning aanstaat zoals de manifests ze zetten: test,
  playground, staging-otc en production-otc, niet meer "niet op productie" (#1119).
