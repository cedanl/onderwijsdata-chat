### Chat: twee bronnen koppelen zonder rijen te verliezen, in code (#988)
- Nieuwe tool `koppel_data`: na `relatie` koppelt de app twee geladen tabellen zelf, op de sleutels die het model
  kiest (bijvoorbeeld brin en croho). Elke rij van beide tabellen blijft staan, ook een opleiding of instelling zonder
  match of zonder score; zo'n rij houdt lege cellen voor de andere bron, nooit 0. De kolom `koppelstatus` zegt per rij
  `beide`, `alleen SKDB` of `alleen DUO`, met een toelichting die het antwoord noemt (andere bron of andere afbakening).
- Eerder schreef het model de koppeling zelf in een script, en verdwenen er rijen (een draaitabel zonder
  `dropna=False`, een filter op een lege score vóór de koppeling, een left join vanuit de verkeerde kant). De
  systeemprompt, de koppelzin van de Studiekeuzedatabase en `relatie` verwijzen nu naar `koppel_data`.
- Geeft de sleutel aan één kant meer rijen per waarde, dan waarschuwt de uitkomst dat waarden van de andere kant per
  rij herhaald staan en niet zomaar opgeteld mogen worden. De download van een koppeling noemt beide bronnen, ook de
  verplichte zin van LCSK, en bevat de kolom `koppelstatus`.
