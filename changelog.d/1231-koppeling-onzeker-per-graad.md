### Chat: de koppeling van de Studiekeuzedatabase met DUO telt zelf, het model neemt over (#1231)
- Koppelt `koppel_data` de Studiekeuzedatabase en DUO op brin en CROHO, dan staat per SKDB-rij in de kolom `onzeker`
  of het NSE-oordeel op minder dan 30 respondenten rust (of op geen bekend aantal), met dezelfde regel als
  `get_studiekeuze`. Bij HU heette een opleiding met 28 respondenten (CROHO 80166) eerder niet onzeker.
- De opleidingen zonder DUO-rij staan per graad geteld in `niet_gekoppeld_per_graad` (bij HU 29 master, 1 bachelor en
  1 associate degree), in plaats van "bijna allemaal masters". Een rij zonder graad telt onder `onbekend`.
- De toelichting bij het resultaat zegt het model de vlag en die aantallen over te nemen en niet zelf te tellen.
