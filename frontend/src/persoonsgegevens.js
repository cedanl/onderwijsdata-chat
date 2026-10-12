// Persoonsgegevens in een vraag herkennen, deterministisch en in code (#478, #191): een BSN
// (negen cijfers die de elfproef doorstaan), een e-mailadres of een Nederlands telefoonnummer.
// Een naam is niet te herkennen; daarom staat de waarschuwing er altijd. De herkenning
// waarschuwt en houdt zulke tekst uit titel en bestandsnaam; ze blokkeert niet.

// Negen losse cijfers: niet midden in een langer of gegroepeerd getal (een telefoonnummer, 1.234.567.890).
const BSN = /(?<!\d)(?<!\d[.,-])\d{9}(?![.,-]?\d)/g
const EMAIL = /[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}/g
// 06 12345678, 030-1234567, +31 6 12345678: tien cijfers vanaf 0, of negen na +31/0031.
const TELEFOON = /(?<![\d+])(?:\+31|0031|0)[\s-]?[1-9](?:[\s-]?\d){8}(?![\d])/g

// De elfproef van een BSN: 9·d1 + 8·d2 + … + 2·d8 − d9 is deelbaar door 11.
export function elfproef(cijfers) {
  if (!/^\d{9}$/.test(cijfers) || /^0{9}$/.test(cijfers)) return false
  const d = [...cijfers].map(Number)
  const som = d.slice(0, 8).reduce((acc, cijfer, i) => acc + cijfer * (9 - i), 0) - d[8]
  return som % 11 === 0
}

const SOORTEN = [
  { soort: 'bsn', patroon: BSN, geldig: elfproef },
  { soort: 'email', patroon: EMAIL, geldig: () => true },
  { soort: 'telefoon', patroon: TELEFOON, geldig: () => true },
]

// Wat er in de tekst staat, per soort: [{ soort, tekst }], in volgorde van de tekst.
export function vindPersoonsgegevens(tekst) {
  const gevonden = []
  for (const { soort, patroon, geldig } of SOORTEN) {
    for (const match of String(tekst ?? '').matchAll(patroon)) {
      if (geldig(match[0])) gevonden.push({ soort, tekst: match[0], index: match.index })
    }
  }
  return gevonden.sort((a, b) => a.index - b.index).map(({ soort, tekst: t }) => ({ soort, tekst: t }))
}

export function bevatPersoonsgegevens(tekst) {
  return vindPersoonsgegevens(tekst).length > 0
}

export const PERSOONSGEGEVENS_WAARSCHUWING = 'Voer geen persoonsgegevens in: je vraag gaat naar een externe AI-dienst.'

const NAMEN = { bsn: 'een BSN', email: 'een e-mailadres', telefoon: 'een telefoonnummer' }

// De melding bij een concept dat persoonsgegevens lijkt te bevatten; null als er niets is gevonden.
export function persoonsgegevensMelding(tekst) {
  const soorten = [...new Set(vindPersoonsgegevens(tekst).map(g => g.soort))].map(s => NAMEN[s])
  if (!soorten.length) return null
  const wat = soorten.length === 1 ? soorten[0] : `${soorten.slice(0, -1).join(', ')} en ${soorten.at(-1)}`
  return `Je vraag lijkt ${wat} te bevatten. Haal dat eruit voordat je verstuurt: de vraag gaat naar een externe AI-dienst en wordt bewaard.`
}
