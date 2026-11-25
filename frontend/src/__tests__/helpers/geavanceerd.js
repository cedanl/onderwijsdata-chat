import { createElement } from 'react'
import { GeavanceerdContext } from '../../geavanceerd'

// Een element onder "Geavanceerd" (#1269): de tests van de code per stap, de CSV-downloads, de technische key en de
// modelkeuze beschrijven die functies zelf, dus met de instelling aan. Zonder deze wikkel staan ze uit, zoals in de app.
export function metGeavanceerd(element, aan = true) {
  return createElement(GeavanceerdContext.Provider, { value: aan }, element)
}
