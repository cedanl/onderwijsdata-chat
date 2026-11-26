### Chat: de vlag `onzeker` en de telling per graad ook bij een koppeling op alleen CROHO (#1273)
- Koppelt `koppel_data` de Studiekeuzedatabase en DUO op alleen CROHO, terwijl beide tabellen al tot één instelling
  (één BRIN) zijn begrensd, dan krijgt de koppeling dezelfde kolom `onzeker` en dezelfde `niet_gekoppeld_per_graad`
  als op brin en CROHO. Bij HU telde het model in die vorm weer zelf.
- Een koppeling op alleen CROHO over meer dan één instelling, of zonder brin-kolom, blijft zoals ze was: zonder vlag
  en zonder telling.
