// Het label "Vaste maat" onder een antwoord (#1242). De server zet het veld alleen als elke datastap van de beurt een
// get_maat was (agent/vaste_maat.py): code, niet het model, bepaalt het. Het zegt welke vaste route het getal gaf,
// niet dat het gecontroleerd of juist is. Een bericht uit localStorage of de gespreksopslag kan iets anders in het veld
// hebben: dan geen label, geen crash.
const VELDEN = ['maat', 'teldefinitie', 'vastgelegd_in', 'vastgelegd_op']

// Het veld zoals de server het stuurde, of null als het er niet is of niet klopt.
export function vasteMaat(waarde) {
  if (!waarde || typeof waarde !== 'object' || Array.isArray(waarde)) return null
  if (!VELDEN.every(v => typeof waarde[v] === 'string' && waarde[v].trim())) return null
  return Object.fromEntries(VELDEN.map(v => [v, waarde[v]]))
}

const DATUM = new Intl.DateTimeFormat('nl-NL', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' })

// 2026-10-14 → 14 oktober 2026; een andere spelling blijft zoals hij is.
export function vastgelegdOp(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso))
  return m ? DATUM.format(new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]))) : String(iso)
}

export const vasteMaatLabel = vm => `Vaste maat: ${vm.maat}`

// Wat het label wel en niet zegt, in één zin: onder het antwoord en in de gespreksexport.
export const VASTE_MAAT_UITLEG =
  'De app haalde dit getal op langs een vaste route: de code koos bron, bestand en codes, niet het model. ' +
  'Dat zegt welke route het getal gaf, niet dat het gecontroleerd is.'

export const vastgelegdTekst = vm => `Vastgelegd in ${vm.vastgelegd_in} op ${vastgelegdOp(vm.vastgelegd_op)}.`
