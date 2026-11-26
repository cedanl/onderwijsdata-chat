// Het voorbehoud van een data-antwoord, zodat het meegaat buiten de app (#1257): het Uitgangspunt (#620), "Niet
// meegeteld" (#743), "Bron en definitie" (#667), elke "Let op"-regel van de controle en de regel "Wat is
// gecontroleerd" (#1260). De kopregels staan als vaste alinea's in de tekst die de server stuurde (agent/run.py,
// _met_kopregels); hier worden ze eruit gelezen, niet opnieuw bedacht. Kopie, gespreksexport, grafiek-CSV en data-CSV
// lezen allemaal deze functies, zodat ze één regel volgen.
import { controleRegelTekst } from './controleRegel'

export const VOORBEHOUD_KOPPEN = ['Uitgangspunt', 'Niet meegeteld', 'Bron en definitie']

// Een alinea die met "**Uitgangspunt:**" (of "**Uitgangspunt**:") begint.
const KOP = new RegExp(`^\\s*\\*\\*(${VOORBEHOUD_KOPPEN.join('|')})(?::\\*\\*|\\*\\*:)\\s*`)

// Markdown-opmaak eruit en op één regel: een '#'-regel in een CSV mag geen regeleinde bevatten.
const plat = tekst => tekst.replace(/\*\*|__|`/g, '').replace(/\s*\n\s*/g, ' ').trim()

// De voorbehoudalinea's uit de tekst, als "Uitgangspunt: …" zonder opmaak, in de volgorde van de tekst.
export function voorbehoudAlineas(content) {
  if (typeof content !== 'string' || !content) return []
  return content.split(/\n\s*\n/).flatMap(alinea => {
    const match = KOP.exec(alinea)
    return match ? [`${match[1]}: ${plat(alinea.slice(match[0].length))}`] : []
  })
}

// Alles wat een export van dit antwoord moet zeggen, als losse regels zonder opmaak.
export function voorbehoudRegels(msg) {
  if (!msg || msg.isError) return []
  return [
    ...voorbehoudAlineas(msg.content),
    ...(Array.isArray(msg.controle) ? msg.controle : []).map(zin => `Let op: ${plat(String(zin))}`),
    controleRegelTekst(msg.controles),
  ].filter(Boolean)
}

// De CSV met de voorbehoudregels als '#'-regels bovenaan (pandas: read_csv(..., comment='#')), na een eventuele BOM.
export function metVoorbehoud(csv, regels) {
  if (!csv || !Array.isArray(regels) || !regels.length) return csv
  const bom = csv.startsWith('﻿') ? '﻿' : ''
  return `${bom}${regels.map(regel => `# ${plat(regel)}`).join('\n')}\n${csv.slice(bom.length)}`
}
