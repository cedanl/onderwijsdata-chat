### Een `/chat#vraag=…`-link vult de invoer ook als de app al open staat (#806)
- Een link met een vraag (#709) werkte alleen als de app opnieuw laadde. Plakte je hem in een tabblad waarin de app al
  draaide, dan veranderde alleen het fragment: de invoer bleef leeg en de vraag stond nog in de adresbalk. Nu leest de
  app ook die wissel, langs hetzelfde pad als bij het opstarten (opschonen, uit de adresbalk, nieuw gesprek, vraag in
  de invoer, onverstuurd, met focus).
- Loopt er op dat moment een antwoord of rapport, dan breekt de link dat niet af: de vraag wacht tot de run klaar is.
