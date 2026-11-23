### Een verduidelijkingsvraag zonder vraag of opties geeft geen lege kaart meer (#1067)
- Riep het model `clarify_scope` aan met kapotte of onvolledige argumenten (ongeldige JSON, geen `vraag`, minder dan twee
  `opties`), dan eindigde de beurt toch en zag de gebruiker een lege bubbel. Nu krijgt het model dezelfde terugmelding
  als bij elke andere tool en gaat de beurt door; alleen een kaart met een vraag en minstens twee opties eindigt de beurt.
