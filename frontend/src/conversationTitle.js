import { bevatPersoonsgegevens } from './persoonsgegevens'

const MAX_TITLE_LENGTH = 80

// Een titel met een BSN, e-mailadres of telefoonnummer zou in de zijbalk, de serverdatabase,
// localStorage en de exportbestandsnaam belanden (#478): dan een generieke titel.
export const TITEL_ZONDER_PERSOONSGEGEVENS = 'Gesprek (persoonsgegevens weggelaten)'

// The first user message becomes the title; strip markup so the sidebar
// shows readable text rather than literal tags.
export function conversationTitle(text) {
  const plain = String(text ?? '').replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim()
  if (bevatPersoonsgegevens(plain)) return TITEL_ZONDER_PERSOONSGEGEVENS
  return plain.slice(0, MAX_TITLE_LENGTH) || 'Nieuw gesprek'
}
