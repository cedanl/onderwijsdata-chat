### Verklaringen alleen op verzoek, in een blok "Niet uit de data" (#1036)
- Een antwoord met data sluit niet meer af met een **Mogelijke verklaring**. De code beslist uit de vraag of de
  gebruiker om een verklaring vraagt ("Waarom daalt ...", "Hoe komt dat?", "Wat is de reden van ...", ook een korte
  vervolgvraag als "En voor wo?" na een waaromvraag). Zonder verzoek is een vermoeden ("een mogelijke verklaring is",
  "het is denkbaar dat") een controleprobleem, ook met voorbehoud: de herkansing haalt het weg.
- Vraagt de gebruiker wel om een verklaring, dan krijgt het antwoord een apart blok **Niet uit de data**: hooguit drie
  toetsbare vragen, elk met een dataset uit de catalogus of "hiervoor is geen bron in deze app". Een oorzaak als feit
  in dat blok, een vierde vraag of een vermoeden buiten het blok geeft een herkansing. Er komt geen extra modelstap bij.
- Een methodische toelichting uit de bron, zoals afronding bij CBS, blijft gewoon in het antwoord. Het rapport toetst
  oorzaken zoals voorheen en krijgt geen antwoordtekst uit de chat mee.
