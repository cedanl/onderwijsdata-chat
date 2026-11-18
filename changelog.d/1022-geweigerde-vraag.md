### Chat: een geweigerde vraag krijgt een weigeringstekst (#1022)
- Sluit de AI-dienst een beurt zonder tekst af als weigering (`finish_reason` `content_filter` of `refusal`), dan ziet
  de gebruiker nu dat de dienst de vraag weigerde, met als voorbeeld code die de server uitleest, en een verwijzing naar
  vragen over de open onderwijsdata. Eerder kwam er de tekst voor een leeg antwoord ("geen antwoord, ook geen
  weigering"), die als storing las.
- De tekst komt uit code: geen bronnen, geen vervolgvragen en geen "Antwoord van <model>" eronder. Een lege respons
  zonder zo'n reden houdt de oude tekst; een antwoord dat halverwege door het filter stopte, blijft staan.
