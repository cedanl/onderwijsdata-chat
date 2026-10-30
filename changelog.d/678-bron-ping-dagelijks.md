### `bron:ping` draait dagelijks in plaats van wekelijks (#678)
- Een bron die verdwijnt of zijn contract wijzigt (zoals RIO v2 → v3, #627) kwam tot een week laat binnen. De
  geplande pipeline draait nu elke dag rond 07:15 op `main`; het blijft één aanroep per bron, zonder LLM.
