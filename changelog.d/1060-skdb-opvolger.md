### Chat: een nieuwe opleiding in de Studiekeuzedatabase heet niet meer "geen DUO-rij" (#1060, #1015)
- De Studiekeuzedatabase toont het aanbod van het komende studiejaar, DUO telt het vorige. Koppelt `koppel_data` de
  twee op brin en CROHO, dan zoekt de app voor een opleiding zonder DUO-rij in RIO op of ze na de DUO-peildatum begint.
  Zo heet HBO-ICT bij Avans (30020) nu "nieuw per 1-9-2026, nog niet in DUO 2025", in plaats van een opleiding die in
  DUO ontbreekt.
- De voorganger staat erbij met zijn eigen aantal uit DUO (bij Avans Informatica, 34479: 928), en wordt nooit bij de
  nieuwe opleiding opgeteld. Een opleiding die doorloopt, zoals Technische Informatica (34475), is geen voorganger.
- De reden staat per rij in de nieuwe kolom `koppelreden` en in het toolresultaat (`opvolgers`); het model formuleert
  alleen. Geeft RIO geen antwoord, dan blijft het "geen DUO-rij" en zegt de koppeling dat het niet is nagegaan.
- `onderwijsbronnen.rio` heeft `onderwijslicenties` en `met_erkenning` (de licenties van een instelling op een
  peildatum, met hun CROHO-code en onderdeel), en `related` volgt nu de next-links van RIO.
