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
// Het eind van de tekst tot nu toe kan het begin van een getal zijn dat nog verder komt ("27." en daarna "135").
// Dat stuk wacht tot het volgende stuk tekst er is.
const STAART = /\d[\d.,\s\u00a0\u202f]*$/

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

// [begin, eind] van elk getal in `tekst` dat moet wachten.
export function wachtendeGetallen(tekst, regel) {
  if (!tekst) return []
  const r = compileer(regel)
  if (!r) return [...tekst.matchAll(ALLE_GETALLEN)].map(m => [m.index, m.index + m[0].length])
  const procenten = [...tekst.matchAll(r.procent)].map(m => [m.index, m.index + m[0].length])
  const getallen = [...tekst.matchAll(r.getal)]
    .filter(m => !procenten.some(([b, e]) => m.index >= b && m.index < e))
    .filter(m => getoetst((m[1] ?? m[0]).replace(r.scheiding, ''), r))
    .map(m => [m.index, m.index + m[0].length])
  return [...procenten, ...getallen].sort((a, b) => a[0] - b[0])
}

// De tekst zonder een getal dat aan het eind nog kan doorlopen.
export function zonderStaart(tekst) {
  return typeof tekst === 'string' ? tekst.replace(STAART, '') : tekst
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
    if (inCode) return [{ type: 'text', value: delen.map(d => d.tekst ?? WACHT_TEKEN).join('') }]
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
