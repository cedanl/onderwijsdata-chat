/**
 * Asserties op toolaanroepen met argumenten (`expected.must_call`, #1243). Puur, zodat score-unit.mjs ze zonder app
 * en zonder LLM toetst.
 *
 * `must_contain_tools` toetst alleen of een tool genoemd is; een antwoord dat het juiste getal noemt via een verkeerde
 * selectie (vorm, jaar, maat) kon zo slagen. Een assertie is `{ tool, args?, min_count? }`, zoals `nao test`:
 * - `tool`: de toolnaam; `a|b` is één van beide;
 * - `args`: een deelverzameling van de input van tool_start. Geneste objecten gaan recursief, een lijst moet gelijk
 *   zijn (zelfde lengte, volgorde en waarden) en een waarde is strikt: 2025 is niet "2025";
 * - `min_count`: hoeveel aanroepen met die args er minstens moeten zijn, standaard 1. `min_count: 0` betekent "mag
 *   niet": dan faalt elke aanroep die past.
 * Een ongeldige assertie (geen lijst, geen tool, een onbekende sleutel, een negatieve of halve min_count) is een fout
 * van de run, nooit een stille pass.
 */

const SLEUTELS = new Set(['tool', 'args', 'min_count'])
const TOOLNAAM = /^[a-z][a-z0-9_]*$/

const isObject = v => v !== null && typeof v === 'object' && !Array.isArray(v)

/** Wat er mis is aan één assertie; leeg is geldig. */
function controleerEen(a) {
  if (!isObject(a)) return ['een assertie moet een object zijn']
  const uit = [...Object.keys(a).filter(k => !SLEUTELS.has(k)).map(k => `onbekende sleutel: ${k}`)]
  if (typeof a.tool !== 'string' || !a.tool.split('|').every(t => TOOLNAAM.test(t))) {
    uit.push('tool moet een toolnaam zijn, of namen met |')
  }
  if ('args' in a && !isObject(a.args)) uit.push('args moet een object zijn')
  if ('min_count' in a && !(Number.isInteger(a.min_count) && a.min_count >= 0)) {
    uit.push('min_count moet een geheel getal van 0 of meer zijn')
  }
  return uit
}

/** De fouten in een must_call-lijst, elk met de plaats; leeg is geldig. */
export function controleerMustCall(lijst) {
  if (!Array.isArray(lijst)) return ['must_call moet een lijst van asserties zijn']
  return lijst.flatMap((a, i) => controleerEen(a).map(f => `must_call[${i}]: ${f}`))
}

/** Strikt gelijk, ook genest: voor lijsten en de waarden erin. */
function gelijk(a, b) {
  if (Array.isArray(a)) return Array.isArray(b) && a.length === b.length && a.every((v, i) => gelijk(v, b[i]))
  if (isObject(a)) {
    return isObject(b) && Object.keys(a).length === Object.keys(b).length && Object.keys(a).every(k => gelijk(a[k], b[k]))
  }
  return a === b
}

/** Staat `verwacht` in `werkelijk`? Objecten als deelverzameling (recursief), lijsten en waarden gelijk. */
export function deelVan(verwacht, werkelijk) {
  if (isObject(verwacht)) {
    return isObject(werkelijk) && Object.entries(verwacht).every(([k, v]) => k in werkelijk && deelVan(v, werkelijk[k]))
  }
  return gelijk(verwacht, werkelijk)
}

/**
 * De uitslag per assertie: { tool, args?, min_count, aantal, geslaagd }, of bij een ongeldige assertie
 * { ongeldig, geslaagd: false }. `aanroepen` zijn de { tool, input } van chatstream.js.
 */
export function toetsMustCall(aanroepen, lijst) {
  if (!Array.isArray(lijst)) return [{ ongeldig: controleerMustCall(lijst)[0], geslaagd: false }]
  return lijst.map(a => {
    const fouten = controleerEen(a)
    if (fouten.length) return { ongeldig: fouten.join('; '), geslaagd: false }
    const namen = a.tool.split('|')
    const min = a.min_count ?? 1
    const aantal = (aanroepen || []).filter(c => namen.includes(c.tool) && (!a.args || deelVan(a.args, c.input))).length
    return { tool: a.tool, ...(a.args && { args: a.args }), min_count: min, aantal, geslaagd: min === 0 ? aantal === 0 : aantal >= min }
  })
}

const aanroepTekst = n => `${n} ${n === 1 ? 'aanroep' : 'aanroepen'}`

/** Eén regel per assertie die faalt, voor `fouten` en de log. */
export function mustCallFouten(uitslag) {
  return (uitslag || []).filter(u => !u.geslaagd).map(u => {
    if (u.ongeldig) return `must_call ongeldig: ${u.ongeldig}`
    const wat = u.args ? `${u.tool} ${JSON.stringify(u.args)}` : u.tool
    return u.min_count === 0
      ? `must_call: ${wat} mag niet: ${aanroepTekst(u.aantal)}`
      : `must_call: ${wat}: ${aanroepTekst(u.aantal)}, minstens ${u.min_count}`
  })
}

/** Moet deze misser blijven staan naast een aanvaarde beperking? Ja bij een verbod of een ongeldige assertie. */
export const altijdFout = u => !u.geslaagd && (u.ongeldig || u.min_count === 0)
