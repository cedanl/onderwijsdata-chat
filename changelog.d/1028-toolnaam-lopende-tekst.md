### Chat: een toolnaam in de lopende tekst kost geen herschrijving meer (#1028)
- Noemde het antwoord een toolnaam in de lopende tekst ("Het totaal is 2.724, berekend met `query_data`."), dan
  schreef het model het antwoord opnieuw: een extra modelronde, en de gebruiker zag de eerste versie verdwijnen (audit
  L-09). Code haalt nu de vaste patronen weg, zoals in de Bronnen-sectie al gebeurde: een haakje met toolnamen
  ("(via `get_rio_instelling`)") en een staart met via/met vlak voor een leesteken ("opgehaald via `get_cbs_data`.").
- Een toolnaam die code niet weg kan halen zonder een kapotte zin achter te laten ("Met query_data heb ik gefilterd op
  2025.", "bevestigd door compute_kpi"), geeft zoals voorheen een herkansing. Tekst in een codeblok of tabel blijft
  ongemoeid.
