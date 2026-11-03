### Inspectieoordelen van vo-scholen als vo-context bij een doorstroomvraag (#881)
- Een nieuwe tool, `get_inspectieoordeel_vo`, geeft de oordelen van de Onderwijsinspectie per afdeling (vmbo, havo, vwo,
  pro) van de vo-scholen in één gemeente, uit het maandelijkse peilbestand per school (po/so/vo, CC0 1.0), met een
  telling per oordeel en de peildatum. Plaats en schoolnaam komen uit DUO's adressen van vo-vestigingen.
- Alleen bij een vraag over doorstroom naar vervolgonderwijs die zelf het vo noemt ("Hoe beoordeelt de inspectie de
  havo/vwo-afdelingen van de scholen waar onze eerstejaars hbo vandaan komen in Utrecht?"). Anders weigert de tool met
  een vaste tekst: bij een mbo-vraag, een hbo-vraag zonder vo-niveau, een losse vo-vraag en buiten de chat. Een vraag
  over één vo-school krijgt nog steeds het vaste vo-antwoord.
- Po- en (v)so-rijen staan wel in het bestand, maar nooit in het resultaat. Het etiket "vo-context voor
  vervolgonderwijs" staat in het resultaat, de bronregel en de Bronnen.
- Het oordeel geldt per afdeling op een vestiging, niet per school of bestuur. "Geen eindoordeel" (69% van de
  vo-afdelingen op 1 november 2026) is geen onvoldoende. Een grote gemeente wordt afgekapt op 25 vestigingen; de
  telling telt alle.
- `get_inspectieoordeel` (mbo) blijft zoals het was. `bron:ping` meet ook het po-so-vo-bestand.
