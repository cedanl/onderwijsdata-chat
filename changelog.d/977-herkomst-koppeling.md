### Een gecombineerde download noemt elke bron, ook LCSK (#977)
- De CSV van een eigen berekening die meer tabellen las, zoals de Studiekeuzedatabase naast DUO, noemt in de kop nu
  elke bron en niet alleen de eerste. Stond DUO vooraan en kwam de Studiekeuzedatabase via `store_get`, dan ontbraken de
  verplichte zin van LCSK, de versie en de link; nu staan ze er in beide volgorden, ook bij een selectie of grafiek op
  zo'n koppeling, na meer stappen en na heropenen van het gesprek. Elke bronregel staat er één keer, met per brontabel de
  inhoudshash of de md5 van het DUO-bestand.
- Zo'n berekening heet onvolledig als één van haar bronnen een afgekapte pagina is, niet alleen de eerste, en ze is zo
  oud als haar oudste bron.
