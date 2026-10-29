### Een time-out van het model krijgt een nieuwe poging (#799)
- Een time-out van de provider (`litellm.Timeout`) ging meteen als fout naar de gebruiker, zonder de melding "Model
  antwoordt traag, nieuwe poging…" en zonder backoff: hij erft niet van de fouten die de herhaling ving. Nu krijgt hij
  dezelfde herhaling als een verbroken verbinding. Hoe lang één modelaanroep mag duren, staat in #800.
