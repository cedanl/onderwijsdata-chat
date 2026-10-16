import { createContext, useContext } from 'react'
import { createPortal } from 'react-dom'

// Op een telefoon is de navbar de enige vaste balk bovenin (#596): een pagina zet er zijn eigen knoppen in,
// zoals de chat de gesprekkenlijst, in plaats van een tweede balk eronder. Nav biedt de plek aan; zolang
// die er niet is (eerste render, of een pagina buiten de shell) rendert dit niets.
export const NavSlotContext = createContext(null)

export function NavSlot({ children }) {
  const slot = useContext(NavSlotContext)
  return slot ? createPortal(children, slot) : null
}
