// De invoer bij "Wijkt af van je eigen cijfer?" (#1258), net als de server (agent/verschilverklaring.invoer): een heel
// getal van hoogstens 12 cijfers. Een punt of spatie mag alleen tussen groepen van drie cijfers (475.460, 475 460),
// zoals in het Nederlands: 1.5 of 475.46 is geen telling. De server toetst opnieuw; dit zegt het alleen eerder.
export const MAX_CIJFERS = 12
export const GEEN_GETAL = 'Geef alleen een heel getal, zonder tekst of decimalen: bijvoorbeeld 475.460.'
export const TE_LANG = `Dat getal is te lang: geef hoogstens ${MAX_CIJFERS} cijfers.`
export const GROEPERING =
  'Een punt of spatie staat alleen tussen groepen van drie cijfers, zoals in 475.460. Geef een heel getal, zonder decimalen.'

// Een spatie als scheiding: ook de harde spaties die een spreadsheet kopieert.
const TEKENS = /^[0-9. \u00a0\u202f]+$/
const HEEL = /^[0-9]+$/
const GEGROEPEERD = /^[0-9]{1,3}(?:\.[0-9]{3})+$|^[0-9]{1,3}(?:[ \u00a0\u202f][0-9]{3})+$/

// null als de invoer een getal is; anders de melding.
export function eigenGetalFout(tekst) {
  const schoon = String(tekst ?? '').trim()
  if (!schoon || !TEKENS.test(schoon)) return GEEN_GETAL
  const kaal = schoon.replace(/[. \u00a0\u202f]/g, '')
  if (!kaal) return GEEN_GETAL
  if (kaal.length > MAX_CIJFERS) return TE_LANG
  if (!HEEL.test(schoon) && !GEGROEPEERD.test(schoon)) return GROEPERING
  return null
}

// Een hoofdgetal zoals de server het in message_end zet: { id, waarde }; anders null.
export function hoofdgetalUit(ev) {
  const h = ev?.hoofdgetal
  return h && typeof h.id === 'string' && h.id && typeof h.waarde === 'number' ? { id: h.id, waarde: h.waarde } : null
}
