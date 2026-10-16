// Een antwoord in markdown als platte tekst voor een schermlezer (#589): zonder de tekens die op het scherm
// opmaak worden (**, #, |, `), een tabelrij als cellen met komma's. Regel voor regel, met regexen zonder
// geneste kwantoren: een lang antwoord vol [ * of | blijft lineair.

const FENCE = /^ {0,3}(?:```|~~~)/
const KOP = /^ {0,3}#{1,6}(?:\s|$)/
const ITEM = /^\s*(?:[-*+]|\d{1,9}[.)])\s+/
const TAAK = /^\[[ xX]\]\s+/
const SCHEIDING = /^(?:-{3,}|\*{3,}|_{3,}|={3,})$/
const TABELSCHEIDING = /^[\s|:-]+$/
const SLOTTEKEN = /[.!?:;]$/

// Afbeelding → alt, link → linktekst; [ en ( komen in de tekst niet voor, zodat een [ zonder ] niet terugzoekt.
const INLINE = [
  [/!\[([^[\]]*)\]\([^()]*\)/g, '$1'],
  [/\[([^[\]]*)\]\([^()]*\)/g, '$1'],
  [/<(https?:[^<>\s]*)>/g, '$1'],
  [/\*/g, ''],
  [/~~/g, ''],
  // _cursief_ en __vet__, niet de underscore in data_key.
  [/(?<![\p{L}\p{N}_])_{1,2}([^_]+)_{1,2}(?![\p{L}\p{N}_])/gu, '$1'],
]

// Inline code houdt zijn tekst; de opmaakregels raken alleen de stukken buiten de backticks.
function inline(regel) {
  return regel.split('`')
    .map((deel, i) => (i % 2 ? deel : INLINE.reduce((tekst, [re, vervang]) => tekst.replace(re, vervang), deel)))
    .join('')
    .trim()
}

const zin = tekst => (!tekst || SLOTTEKEN.test(tekst) ? tekst : `${tekst}.`)

function zonderSluitHekjes(tekst) {
  const kaal = tekst.trimEnd()
  let eind = kaal.length
  while (eind > 0 && kaal[eind - 1] === '#') eind--
  return eind === 0 || /\s/.test(kaal[eind - 1]) ? kaal.slice(0, eind) : kaal
}

function tabelrij(regel) {
  return zin(regel.split('|').map(inline).filter(Boolean).join(', '))
}

function regelTekst(ruw) {
  const regel = /^\s*>/.test(ruw) ? ruw.replace(/^[\s>]+/, '') : ruw
  const kaal = regel.replace(/\s/g, '')
  if (SCHEIDING.test(kaal)) return ''
  if (regel.includes('|')) return TABELSCHEIDING.test(regel) ? '' : tabelrij(regel)
  if (KOP.test(regel)) return zin(inline(zonderSluitHekjes(regel.trimStart().replace(/^#+/, ''))))
  if (ITEM.test(regel)) return zin(inline(regel.replace(ITEM, '').replace(TAAK, '')))
  return inline(regel)
}

// Een codeblok wordt niet voorgelezen; een blok zonder slot loopt door tot het eind, zoals in markdown.
function zonderCodeblokken(regels) {
  let inBlok = false
  return regels.filter(regel => {
    if (FENCE.test(regel)) {
      inBlok = !inBlok
      return false
    }
    return !inBlok
  })
}

export function platteTekst(markdown) {
  if (typeof markdown !== 'string' || !markdown.trim()) return ''
  return zonderCodeblokken(markdown.split('\n')).map(regelTekst).filter(Boolean).join('\n')
}
