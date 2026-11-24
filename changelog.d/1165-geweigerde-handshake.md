### De API-referentie zegt wat een client ziet bij een geweigerde chatverbinding (#1165)
- `docs/api.md` noemde `4001` ("bij het verbinden") en `4003` als sluitcodes, maar de server sluit in die gevallen vóór
  het accepteren: uvicorn maakt er een HTTP 403 op de handshake van, een Python-client ziet `InvalidStatus` en een
  browser een kale `1006`. De referentie zegt dat nu, en noemt `4001` alleen als sluitcode ná het verbinden, voor een
  actie die een run start. Het gedrag van de server is niet veranderd.
