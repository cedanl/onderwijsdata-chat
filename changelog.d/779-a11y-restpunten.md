### Kleine a11y-restpunten in de gesprekslijst en de instellingen (#779)
- Het veld voor een nieuwe gespreksnaam stond binnen de gespreksknop: ongeldige HTML, waarin browsers focus en toetsen
  verschillend behandelen. Tijdens het hernoemen is de rij nu geen knop; het veld heeft een naam voor de schermlezer,
  is op een aanraakscherm 44 px hoog (was 24 px) en na Enter of Escape gaat de focus terug naar het gesprek.
- De themaknoppen (Systeem, Licht, Donker) zeggen met `aria-pressed` welke gekozen is, zoals de functieknoppen ernaast.
- Zoeken in gesprekken toont hoogstens 50 treffers, nieuwste eerst. Bij een volle pagina staat er nu dat oudere
  treffers kunnen ontbreken en dat een preciezere zoekterm helpt; eerder leek het alles.
- De melding "Ingeladen gesprek" is op een telefoon 12,5 px (was 11,7 px), zoals de andere kleine lagen (#613/#663).
