### Een onderdrukte cel rekent de app niet terug (#1265)
- Een DUO-cel met -1 of een CBS-cel met '.' is vaak terug te rekenen als totaal min de zichtbare delen, uit een
  totaalrij of een totaalbestand. `run_analysis` en `compute_kpi` geven dan "Deze cel is door de bron onderdrukt;
  terugrekenen geven we niet." in plaats van het getal, ook in een tabel of grafiek; een antwoord dat het getal zelf
  uitrekent, houdt de controle in.
- Een verschil van twee totalen die allebei de onderdrukte cel bevatten, blijft gewoon mogelijk.
- Twee nieuwe kritieke weigeringen in de evals (`weigering-terugrekenen-duo`, `weigering-terugrekenen-cbs`).
