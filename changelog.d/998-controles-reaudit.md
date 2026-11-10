### Minder onterecht herschreven antwoorden, en een rekensom wordt nagerekend (#998, #999, #1000, #1001)
- Een CBS-totaal zonder T00-code, zoals 'Opleidingsfase totaal' of 'Totaal mbo (incl extranei)', telt nu als totaal:
  "alle opleidingsfasen" of "alle leerwegen" bij zo'n selectie is geen fout meer, en het uitgangspunt noemt zo'n
  totaal niet meer. Een deeltotaal als 'Totaal (speciaal) basisonderwijs' of 'Totaal mbo (excl. extranei)' blijft een
  vastgelegde waarde (#998).
- Een antwoord dat zegt dat iets in de Studiekeuzedatabase niet staat, nadat die bron wel is opgehaald, gaat niet meer
  onterecht terug met "niet opgehaald": de controle vergelijkt het ID uit de vraag en dat van de lading nu op één
  manier (`bron:id`). Is een genoemde dataset echt niet opgehaald, dan noemt de opdracht aan het model de tool die hem
  ophaalt (get_studiekeuze, get_cbs_data, ...) in plaats van een vaste lijst van drie (#999).
- "Ik heb de oorzaak niet gecontroleerd", "de oorzaak is niet onderzocht" en "ik weet de oorzaak niet" gelden nu als
  voorbehoud en niet meer als een gegeven oorzaak; "De oorzaak is de coronapandemie." blijft een probleem (#1000).
- Een uitgeschreven rekensom in een chatantwoord wordt nagerekend: "3 × 3 × 3 × 4 × 15 = 540 combinaties" geeft een
  herkansing met "3 × 3 × 3 × 4 × 15 is 1.620, niet 540", en blijft de som fout, dan wordt het antwoord ingehouden.
  Afronden op de decimalen van de uitkomst mag ("571 / 8.060 × 100 = 7,1"); een schooljaar als 2024/25 is geen deling
  en een som met "ongeveer", "circa" of "≈" wordt niet nagerekend (#1001).
