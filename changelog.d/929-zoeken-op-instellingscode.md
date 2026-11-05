### Een dashboard vindt een instelling ook op haar instellingscode (#929)
- `/api/dashboard/regio?instelling=21CY` gaf "niet gevonden" zonder suggesties, terwijl `/api/instellingen` die code
  zelf meelevert. De dashboards en het instellingsprofiel zoeken nu ook op de instellingscode (BRIN), hoofdletterongevoelig.
  Een instelling met meer codes in DUO (Curio: 21CY en 25LX) is onder elke code te vinden; het register noemt ze alle
  in `instellingscodes`.
- Lijkt een onbekende naam op geen enkele instelling, dan zegt het dashboard waarop je kunt zoeken (naam, afkorting of
  instellingscode) in plaats van alleen "niet gevonden".
