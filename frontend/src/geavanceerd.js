import { createContext, useContext } from 'react'
import { STORAGE_GEAVANCEERD } from './constants'

// De instelling "Geavanceerd" (#1269): extra mogelijkheden voor wie de analyse zelf wil zien en bijsturen, standaard
// uit. Ze voegt alleen iets toe (de code per stap, de technische key van een getal, de CSV-downloads met "Vraag opnieuw
// stellen", de code in de gespreksexport en de modelkeuze) en verbergt nooit een beschermende functie
// (docs/kwaliteit-en-veiligheid.md; beschermingInvariant.test.js bewaakt dat).
//
// Met login staat de keuze op de server, per account (/api/mijn-gegevens/geavanceerd); App.jsx haalt haar op en geeft
// haar via deze context door. Zonder login is er geen eigen account: dan houdt deze browser haar zelf.
// Zonder Provider uit: een onderdeel buiten App toont dan niets extra's.
export const GeavanceerdContext = createContext(false)

export function useGeavanceerd() {
  return useContext(GeavanceerdContext) === true
}

// Zonder login: de keuze van deze browser, standaard uit.
export function laadLokaal() {
  try { return localStorage.getItem(STORAGE_GEAVANCEERD) === '1' } catch { return false }
}

export function bewaarLokaal(aan) {
  try {
    if (aan) localStorage.setItem(STORAGE_GEAVANCEERD, '1')
    else localStorage.removeItem(STORAGE_GEAVANCEERD)
  } catch { /* noop */ }
}
