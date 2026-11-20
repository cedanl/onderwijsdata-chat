### Rapportchecklist: de lijst blijft open, en een meegetrokken vraag staat aangevinkt (#1045)
- Op een telefoon klapte de lijst dicht zodra je van vijf naar vier figuren ging, onder je vinger. De lijst opent nog
  steeds vanzelf bij te veel figuren, maar klapt nu alleen dicht als je dat zelf doet.
- Gebruikt een figuur ook data uit een andere vraag (bijvoorbeeld een analyse die een eerdere tabel las), dan nam de
  server die vraag mee in het rapport terwijl ze in de lijst uit stond. Nu stuurt de server per figuur alle vragen mee
  waar ze op rust (`beurten` in `report_checklist`): een figuur aanzetten vinkt ze allemaal aan, en zo'n vraag zegt
  "Nodig voor figuur “…”". Zet je die vraag uit, dan gaat de figuur ook uit.
- Twee figuren met dezelfde titel krijgen een volgnummer in hun label, bijvoorbeeld "Instroom (1)" en "Instroom (2)".
