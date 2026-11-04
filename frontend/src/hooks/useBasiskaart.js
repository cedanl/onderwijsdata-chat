import { useEffect, useState } from 'react'
import { basiskaartNaam, heeftBasiskaart, laadBasiskaart } from '../basiskaart'

// Of de basiskaart van een geo-figuur klaarstaat voor Plotly (#906): 'klaar' zonder geo-subplot, of als de app de
// kaart meelevert en die geladen is; 'bezig' zolang hij laadt. Een kaart die de app niet meelevert is meteen 'klaar':
// Plotly zoekt hem dan zelf, en een mislukte kaart meldt zich via onError (KaartSection).
export function useBasiskaart(geo) {
  const naam = geo ? basiskaartNaam(geo) : null
  const nodig = Boolean(naam && heeftBasiskaart(naam))
  const [geladen, setGeladen] = useState(null)
  useEffect(() => {
    if (!nodig) return
    let weg = false
    laadBasiskaart(naam)
      .catch(() => false)
      .then(() => { if (!weg) setGeladen(naam) })
    return () => { weg = true }
  }, [naam, nodig])
  return !nodig || geladen === naam ? 'klaar' : 'bezig'
}
