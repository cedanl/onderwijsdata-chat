// De invoer bij "Wijkt af van je eigen cijfer?" (#1258), net als de server (agent/verschilverklaring.invoer): een heel
// getal, met punten of spaties als scheiding van duizendtallen, hoogstens 12 cijfers. De server toetst opnieuw; dit
// zegt het alleen eerder, zonder rondgang.
export const MAX_CIJFERS = 12
export const GEEN_GETAL = 'Geef alleen een heel getal, zonder tekst of decimalen: bijvoorbeeld 475.460.'
export const TE_LANG = `Dat getal is te lang: geef hoogstens ${MAX_CIJFERS} cijfers.`

// null als de invoer een getal is; anders de melding.
export function eigenGetalFout(tekst) {
  const kaal = String(tekst ?? '').trim().replace(/[.\s]/g, '')
  if (!/^[0-9]+$/.test(kaal)) return GEEN_GETAL
  if (kaal.length > MAX_CIJFERS) return TE_LANG
  return null
}

// Een hoofdgetal zoals de server het in message_end zet: { id, waarde }; anders null.
export function hoofdgetalUit(ev) {
  const h = ev?.hoofdgetal
  return h && typeof h.id === 'string' && h.id && typeof h.waarde === 'number' ? { id: h.id, waarde: h.waarde } : null
}
