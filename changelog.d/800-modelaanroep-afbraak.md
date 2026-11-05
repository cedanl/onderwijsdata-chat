### `MODELAANROEP` telt ook de aanroepen die de tijdsgrens afbrak (#800)
- Een modelaanroep die na de harde grens van de run (`RUN_TIMEOUT_S` plus de uitloop) of van het rapport
  (`GENEREER_TIMEOUT_S`) werd afgebroken, logde `uitkomst=ok`: de afbraak (`CancelledError`) viel buiten de foutafhandeling.
  Juist de vastzittende aanroepen ontbraken zo in de meting voor `LITELLM_REQUEST_TIMEOUT`.
- Zo'n aanroep logt nu `uitkomst=afgebroken_runlimiet`, met in `totaal` de duur tot de afbraak. Een annulering van buitenaf
  (gesloten WebSocket, reset, ander gesprek) logt `uitkomst=geannuleerd`. De annulering gaat daarna gewoon door, en elke
  aanroep houdt precies één regel.
- `LITELLM_REQUEST_TIMEOUT` blijft 1200 s; de waarde volgt na de hermeting.
