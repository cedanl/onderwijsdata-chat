import { createContext, useContext } from 'react'

// Welke bron met een omgevingsregel hier antwoord geeft (/api/config `bronnen`, tools/beschikbaarheid.py, #956), voor
// de pagina's onder App die een kaart op zo'n bron hebben: de financiën en het personeel op Mijn instelling (#935,
// #936). Zonder provider, of zolang /api/config niet antwoordde, staat geen bron aan: de kaart vraagt dan niets op.
export const BronnenAan = createContext({})

export function useBronAan(naam) {
  return useContext(BronnenAan)?.[naam] === true
}
