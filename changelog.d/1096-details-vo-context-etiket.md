### Catalogus: de details van een vo-contexttabel dragen het etiket (#1096)
- `dataset_details` van een vo-contexttabel (85379NED, 85566NED en de andere acht) geeft nu hetzelfde veld `context`
  als de zoektreffer: "vo-context voor vervolgonderwijs: leerlingen in het voortgezet onderwijs (ook vavo en vsv), geen
  mbo- of ho-studenten". Eerder stond dat alleen bij een zoektreffer, terwijl een direct dataset-ID zonder zoekpoort
  laadt en een MCP-client vaak meteen de details vraagt.
