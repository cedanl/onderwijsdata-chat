### Het voorbehoud reist mee in kopie, CSV en rapport (#1257)
- De kopieerknop, de gespreksexport, de CSV bij een grafiek en de data-CSV nemen het Uitgangspunt, "Niet meegeteld",
  "Bron en definitie", elke "Let op"-regel en de regel "Wat is gecontroleerd" mee. In een CSV staan ze als regels met
  `#` boven de tabel: `read_csv(..., comment='#')` leest de tabel ongewijzigd.
- Een tabel met onderdrukte cellen krijgt de kolom `ondergrens`: `ja` als er in die rij een onderdrukte cel valt, anders
  `nee`. Onder de CSV-knoppen zegt "Wat staat er in de CSV?" wat de regels en de kolom betekenen.
- In het rapport, de PDF-afdruk en het Word-document staat de bron in de figuur zelf, met "ten minste" als een
  onderdrukte cel meetelt. In de chat staat die regel niet in de grafiek, maar eronder.
