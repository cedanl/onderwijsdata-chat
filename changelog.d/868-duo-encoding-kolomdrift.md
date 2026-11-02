### DUO-bestanden in cp1252 laden en een gewijzigde kolom melden (#868)
- Een DUO-bestand in cp1252 faalde met een leesfout; de chat probeert het nu opnieuw in cp1252 (`DUO_ENCODING` in het
  log).
- Wijken de kolommen van een geladen DUO-bestand af van het schema dat de chat kent (een hernoemde, verdwenen of
  nieuwe kolom), dan staat dat als waarschuwing in het resultaat en als `DUO_SCHEMA_DRIFT` in het log. Een hernoemde
  codekolom kon zo ongemerkt als getal worden gelezen, zonder voorloopnullen.
