### Een mbo-instelling met meer instellingscodes telt in de chat en via MCP over alle codes (#1069)
- `get_maat` `mbo_studenten_instelling` en de MCP-tools `aantallen_per_jaar` en `vergelijk_instellingen` telden bij een
  instelling met twee DUO-codes alleen de eerste: Curio (21CY en 25LX) kreeg 901 studenten in 2025/26 in plaats van
  15.288. Nu tellen ze over alle codes, net als het dashboard Mijn instelling, en vraag je met de naam of met een van
  de codes, dan krijg je dezelfde reeks.
- Het recept en het bewijs noemen beide codes als filter (`INSTELLINGSCODE: ["21CY", "25LX"]`); de MCP-uitvoer noemt
  ze onder `instelling.instellingscodes`. Instellingen met één code houden dezelfde uitkomst.
