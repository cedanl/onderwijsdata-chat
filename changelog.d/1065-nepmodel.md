### Lokaal testen zonder API-sleutel met het nepmodel (#1065)
- Met `MODEL=mock/default` (of `mock/tekst`) draait de chat lokaal zonder providersleutel: vraag, toolstappen, antwoord
  en rapport werken met de echte app en toollaag, alleen het model geeft vaste antwoorden. De model-picker toont de
  scenario's.
- Alleen voor `APP_ENV` `local` en `development`; op test, playground en productie start de app niet met een
  `mock/`-model, ook niet via `AVAILABLE_MODELS` of `USER_MODELS`.
- Een Playwright-test (`tests/e2e/mock-llm.spec.js`) loopt de hele chat met het nepmodel door, in CI zonder secrets.
