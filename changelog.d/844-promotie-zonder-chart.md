### `promotie.py promote` weigert release 2.0.0 (#844)
- De tag `2.0.0` heeft geen chart; een pin erop laat Flux falen. `scripts/promotie.py promote --version 2.0.0` stopt
  nu met een melding in plaats van de pin te schrijven. `docs/promoten.md` gebruikt `X.Y.Z` als voorbeeld, niet meer
  `2.0.0`.
