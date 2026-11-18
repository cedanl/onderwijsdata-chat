### Rapporten: download als bewerkbaar Word-document (#1038)
- Naast "Download als HTML", "Download als Markdown" en "Opslaan als PDF" staat bij een geopend rapport "Download als
  Word" (op een telefoon in het ⋯-menu). Het `.docx` volgt het rapport: titel, datum en instelling, afwijking van je
  vraag, onderzoeksvraag, reikwijdte, definities, per visualisatie de grafiek met noot, bronregel en toelichting, de
  conclusie met koppen, vet, opsommingen en tabellen als echte Word-tabel, de bronnen en de herkomst. Zo kun je de
  uitkomsten aanvullen met eigen bevindingen (vervolg op de Markdown-export van #746).
- Het document is in Npuls-huisstijl (`templates/rapport.docx`, gebouwd met `scripts/maak_rapportsjabloon.py` en in
  Word bij te werken): koppen in oranje, General Sans met terugval op Inter of Arial, het Npuls-beeldmerk en
  openEDUdata+ in de kop, paginanummers in de voet.
- De server maakt het document uit het bewaarde rapport (`POST /api/workbooks/{id}/docx`); de browser stuurt alleen
  de grafieken als PNG mee, en die worden niet bewaard. Lukt een grafiek niet, dan staat er "Grafiek niet beschikbaar"
  en komt het document toch.
