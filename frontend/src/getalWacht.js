// Getallen pas na de controle (#1254). De tekst stroomt live binnen, maar de getalcontrole van de server draait
// pas na de modelronde: een verzonnen getal stond zo even in beeld voor het werd ingetrokken. Tijdens het streamen
// staat elk getal dat die controle toetst (vier of meer cijfers, geen jaartal, of een percentage) daarom als "…" in
// de tekst, tot message_end. Jaartallen en getallen onder 1.000 blijven zichtbaar: die toetst de controle niet.
//
// De regel komt van de server, bij elke message_start (`getalregel`, agent/grounding.py): één bron voor de
// controle en het scherm. Zonder regel (een oude server) wacht elk getal, ook een jaartal: liever te veel dan een
// ongecontroleerd getal.

export const WACHT_LABEL = 'getal wordt gecontroleerd'
export const WACHT_TEKEN = '…'

// Zonder regel: elke reeks cijfers, met scheidingstekens en een procentteken erbij.
const ALLE_GETALLEN = /\d+(?:[.,\s\u00a0\u202f]\d+)*(?:\s?(?:%|procent\b))?/g
// Het eind van de tekst tot nu toe kan het begin zijn van een getal dat nog verder komt ("27." en daarna "135"), of
// van een percentage waarvan het woord nog binnenkomt ("70,6 pro" en daarna "cent"). Dat stuk wacht tot het volgende
// stuk tekst er is. Een half woord na het getal wacht als het een procentteken van de server kan worden
// (`procenttekens`); zonder die lijst wacht elk half woord na een getal.
const IN_GETAL = /[\d.,\s\u00a0\u202f]/
const LETTER = /\p{L}/u
// De controle toetst het antwoord zoals de gebruiker het na message_end ziet (`lezingen` in agent/controles.py): 9.5%
// wordt 9,5%, en in een Engels antwoord is 12,345 twaalfduizend. De stroom is nog de notatie van het model. Daarom
// wacht ook wat de regel in de andere notatie vindt: punt en komma tussen cijfers verwisseld, op dezelfde plek.
const TUSSEN_CIJFERS = /(?<=\d)[.,](?=\d)/g

// Elk begin van een procentteken, zonder het hele teken: dat vindt de regel `procent` zelf al. Null zonder bruikbare
// lijst: dan telt elk half woord.
function halveTekens(tekens) {
  if (!Array.isArray(tekens) || !tekens.every(t => typeof t === 'string' && t)) return null
  return tekens.flatMap(t => Array.from({ length: t.length - 1 }, (_, i) => t.slice(0, i + 1)))
}

// Waar het stuk aan het eind begint dat nog een getal of een percentage kan worden; de lengte van de tekst als er geen
// is. Van achteren naar voren, zonder patroon dat bij elke positie opnieuw zoekt: een lange reeks cijfers en
// komma's ("1, 2, 3, …") kostte zo bij elke render kwadratisch veel tijd.
function staartBegin(tekst, halven) {
  const eindes = [tekst.length]
  if (halven) {
    eindes.push(...halven.filter(h => tekst.endsWith(h)).map(h => tekst.length - h.length))
  } else {
    let eind = tekst.length
    while (eind > 0 && LETTER.test(tekst[eind - 1])) eind--
    eindes.push(eind)
  }
  let staart = tekst.length
  for (const eind of eindes) {
    let begin = eind
    while (begin > 0 && IN_GETAL.test(tekst[begin - 1])) begin--
    const cijfer = tekst.slice(begin, eind).search(/\d/)
    if (cijfer >= 0) staart = Math.min(staart, begin + cijfer)
  }
  return staart
}

const regels = new WeakMap()

function compileer(regel) {
  if (!regel || typeof regel !== 'object') return null
  if (regels.has(regel)) return regels.get(regel)
  let uit = null
  try {
    const [laag, hoog] = Array.isArray(regel.jaren) ? regel.jaren : []
    if (typeof regel.getal === 'string' && typeof regel.procent === 'string' && Number.isInteger(regel.min_cijfers)) {
      uit = {
        getal: new RegExp(regel.getal, 'g'),
        procent: new RegExp(regel.procent, 'g'),
        scheiding: new RegExp(typeof regel.scheiding === 'string' ? regel.scheiding : '[. \u00a0\u202f]', 'g'),
        minCijfers: regel.min_cijfers,
        laag: Number.isInteger(laag) ? laag : null,
        hoog: Number.isInteger(hoog) ? hoog : null,
        halven: halveTekens(regel.procenttekens),
      }
    }
  } catch {
    uit = null
  }
  regels.set(regel, uit)
  return uit
}

// De regel uit een message_start, of null als er geen bruikbare is.
export function regelUit(ev) {
  return compileer(ev?.getalregel) ? ev.getalregel : null
}

function getoetst(cijfers, r) {
  if (cijfers.length < r.minCijfers) return false
  const n = Number(cijfers)
  return !(r.laag !== null && r.hoog !== null && n >= r.laag && n <= r.hoog)
}

function getoetsteGetallen(tekst, r) {
  const procenten = [...tekst.matchAll(r.procent)].map(m => [m.index, m.index + m[0].length])
  const getallen = [...tekst.matchAll(r.getal)]
    .filter(m => !procenten.some(([b, e]) => m.index >= b && m.index < e))
    .filter(m => getoetst((m[1] ?? m[0]).replace(r.scheiding, ''), r))
    .map(m => [m.index, m.index + m[0].length])
  return [...procenten, ...getallen]
}

function samengevoegd(plekken) {
  const uit = []
  for (const [begin, eind] of plekken.sort((a, b) => a[0] - b[0])) {
    const vorige = uit.at(-1)
    if (vorige && begin < vorige[1]) vorige[1] = Math.max(vorige[1], eind)
    else uit.push([begin, eind])
  }
  return uit
}

// [begin, eind] van elk getal in `tekst` dat moet wachten.
export function wachtendeGetallen(tekst, regel) {
  if (!tekst) return []
  const r = compileer(regel)
  if (!r) return [...tekst.matchAll(ALLE_GETALLEN)].map(m => [m.index, m.index + m[0].length])
  const verwisseld = tekst.replace(TUSSEN_CIJFERS, teken => (teken === '.' ? ',' : '.'))
  return samengevoegd([...getoetsteGetallen(tekst, r), ...getoetsteGetallen(verwisseld, r)])
}

// De tekst zonder een getal dat aan het eind nog kan doorlopen, of nog een percentage kan worden.
export function zonderStaart(tekst, regel) {
  return typeof tekst === 'string' ? tekst.slice(0, staartBegin(tekst, compileer(regel)?.halven ?? null)) : tekst
}

// De stukken van `tekst`: { tekst } of { wacht: lengte } voor een getal dat wacht.
export function stukken(tekst, regel) {
  const uit = []
  let vanaf = 0
  for (const [begin, eind] of wachtendeGetallen(tekst, regel)) {
    if (begin > vanaf) uit.push({ tekst: tekst.slice(vanaf, begin) })
    uit.push({ wacht: eind - begin })
    vanaf = eind
  }
  if (vanaf < tekst.length) uit.push({ tekst: tekst.slice(vanaf) })
  return uit
}

// De tekst zoals ze in beeld staat: elk getal dat wacht als "…" (voor de kopieerknop).
export function zoalsGetoond(tekst, regel) {
  return stukken(tekst, regel).map(d => d.tekst ?? WACHT_TEKEN).join('')
}

function wachtElement(lengte) {
  return {
    type: 'element',
    tagName: 'span',
    properties: {
      className: ['getal-wacht'],
      role: 'img',
      ariaLabel: WACHT_LABEL,
      ariaBusy: 'true',
      // Even breed als het getal: de regel verspringt niet als het verschijnt.
      style: `width: ${lengte}ch`,
    },
    children: [{ type: 'text', value: WACHT_TEKEN }],
  }
}

function vervang(node, regel, inCode) {
  if (!Array.isArray(node.children)) return
  node.children = node.children.flatMap(kind => {
    if (kind.type !== 'text') {
      vervang(kind, regel, inCode || kind.tagName === 'code' || kind.tagName === 'pre')
      return [kind]
    }
    const delen = stukken(kind.value, regel)
    if (!delen.some(d => d.wacht)) return [kind]
    // In code geen element: het codeblok leest zijn tekst als string. Daar staat alleen het teken.
    if (inCode) return [{ type: 'text', value: zoalsGetoond(kind.value, regel) }]
    return delen.map(d => (d.wacht ? wachtElement(d.wacht) : { type: 'text', value: d.tekst }))
  })
}

// Rehype-plugin voor react-markdown: elk getal dat wacht, wordt een "…" met de toegankelijke naam WACHT_LABEL.
export function rehypeGetalWacht(regel) {
  return () => tree => vervang(tree, regel, false)
}

// Wacht dit bericht nog op de controle? Tijdens het streamen, en een antwoord dat afbrak voor message_end: dat
// heeft de controle nooit gezien.
export function wachtOpControle(msg) {
  return msg?.role === 'assistant' && (!msg.done || !!msg.interrupted)
}
