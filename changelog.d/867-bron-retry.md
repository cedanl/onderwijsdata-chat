### Een tijdelijke storing bij CBS, DUO of RIO wordt opnieuw geprobeerd (#867)
- Een HTTP 5xx, een 429 of een verbroken verbinding was meteen een bronfout in het antwoord, terwijl dezelfde aanroep
  een seconde later slaagde. De chat probeert zo'n ophaalactie nu hooguit twee keer opnieuw, met een korte, oplopende
  wachttijd, en alleen zolang dat binnen 30 seconden na de eerste poging past. Elke herhaling staat als `BRON_RETRY`
  in het log.
- Een fout van de aanvraag zelf (400, 404) wordt niet herhaald. Een fout die blijft, ook de HTTP 500 die CBS geeft op
  een filter met twee haakjesgroepen (#561), geeft dezelfde melding als voorheen.
