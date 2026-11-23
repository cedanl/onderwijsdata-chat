### API: een onverwachte fout geeft een Nederlandse JSON-500 met fout-ID en security-headers (#1154)
- Een uitzondering die een REST-route niet afving gaf een kale `text/plain` "Internal Server Error", zonder
  security-headers en zonder `Cache-Control: no-store`, met een traceback van ± 125 regels in het log. Het antwoord is nu
  een 500 in JSON met dezelfde vaste tekst en hetzelfde fout-ID als in de chat, en draagt de headers van elk ander
  `/api`-antwoord.
- Het log krijgt op ERROR één regel met fout-ID, het pad van de route, het type en een kenmerk van de uitzondering
  (geen tekst, die kan bij PostgreSQL host en databasenaam bevatten); de traceback staat onder hetzelfde ID op DEBUG.
