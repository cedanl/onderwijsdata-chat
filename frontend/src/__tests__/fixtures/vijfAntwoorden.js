// Vijf keer dezelfde V1-vraag (CH-09, #416): hetzelfde getal en dezelfde reeks, maar 0 of 9
// citaties, 3 of 4 CSV-knoppen, wel of geen Telling-blok en 1 of 2 bronnen.
const TEKST = 'De Hogeschool Utrecht had in 2024/25 7.912 eerstejaars, tegen 8.304 in 2020/21.'
const TELLING = '\n\n**Telling**\n- p01hoinges (Ingeschrevenen hoger onderwijs): Ingeschrevenen: hoofdinschrijvingen op 1 oktober. Een hbo-inschrijving telt niet ook in het wo.'
const DUO = 'DUO · Ingeschrevenen hoger onderwijs, 2020/21 t/m 2024/25 (p01hoinges)'
const CBS = 'CBS · Hoger onderwijs; ingeschrevenen (85423NED)'

const stap = exportKey => ({ name: 'query_data', label: 'Data gefilterd', done: true, exportKey })
const stappen = n => Array.from({ length: n }, (_, i) => stap(`duo:p01hoinges:0:${i}`))

// n citaties, waarvan `onbepaald` zonder vastgestelde herkomst.
const citaties = (n, onbepaald = 0) =>
  Array.from({ length: n }, (_, i) =>
    i < onbepaald
      ? { getal: '8.304', vastgesteld: false, reden: 'geen_meetwaarde' }
      : { getal: '7.912', vastgesteld: true, stap: 2, tool: 'query_data', bron: DUO, maat: 'Aantal' })

const antwoord = ({ cites, tabellen, telling, bronnen }) => ({
  role: 'assistant',
  done: true,
  content: telling ? TEKST + TELLING : TEKST,
  tools: stappen(tabellen),
  citaties: cites,
  bronnen,
})

export const VIJF_ANTWOORDEN = [
  antwoord({ cites: [], tabellen: 3, telling: true, bronnen: [DUO] }),
  antwoord({ cites: citaties(9, 2), tabellen: 4, telling: true, bronnen: [DUO, CBS] }),
  antwoord({ cites: citaties(9), tabellen: 3, telling: false, bronnen: [DUO] }),
  antwoord({ cites: [], tabellen: 4, telling: false, bronnen: [DUO, CBS] }),
  antwoord({ cites: citaties(9, 1), tabellen: 3, telling: true, bronnen: [DUO] }),
]

// Een dataantwoord met alleen citaties: telling, export en bronnen zijn n.v.t.
export const ALLEEN_CITATIES = antwoord({ cites: citaties(2), tabellen: 0, telling: false, bronnen: [] })

export { TEKST, TELLING, DUO, CBS }
