### Nieuw dashboard Opleidingen voor hogescholen en universiteiten, op test en playground (#957)
- Per opleiding en vorm van de eigen instelling: het oordeel van studenten (NSE) met het aantal respondenten, studenten,
  eerstejaars, doorstroom naar jaar 2, diplomarendement en numerus fixus, met het landelijke cijfer van LCSK ernaast. De
  tabel staat op naam en sorteert op naam, graad, vorm of plaats: het dashboard rangschikt geen opleidingen of
  instellingen en geeft geen oordeel boven of onder landelijk.
- De tien NSE-thema's per vorm achter een uitklap, de numerus-fixuslijst met capaciteit, studiejaar en voertaal, en per
  opleiding de arbeidsmarkt van de opleidingsrichting (mediaan salaris, werkloosheid, baan op niveau, aansluiting
  studie-baan): landelijke cijfers per rubriek, niet over de eigen afgestudeerden, en niet voor een wo-bachelor.
- Een oordeel op minder dan 30 respondenten heet onzeker, zoals in de chat; een leeg vak is "geen cijfer", nooit 0.
- Het bronblok noemt versie, NSE-jaar en 1cijferHO-jaar van de export en de verplichte vermelding van LCSK met link.
  De verantwoording staat in de documentatie (Dashboards).
- Alleen waar de sleutel van de Studiekeuzedatabase staat; elders staat het dashboard niet in de galerij. Een
  mbo-instelling krijgt een vaste melding: de bron heeft alleen hbo en wo. Chat en dashboard delen één lading van de
  export.
- Nieuw eindpunt `/api/dashboard/opleidingen`.
