// Het rapport als Markdown (#746): de tekst om in een eigen document aan te vullen, naast "Download als HTML" en
// "Opslaan als PDF". Dezelfde volgorde als het rapport (reportHtml.js); een lege sectie valt weg. Een grafiek kan
// niet mee (een .docx met grafieken als afbeelding komt pas als daar vraag naar blijft): per visualisatie staat
// dat er een grafiek stond, met titel, noot, bron en toelichting. De invoer komt uit rapportUitHtml.js.
export const GRAFIEK_REGEL = '_Hier staat in het rapport een grafiek. Die zit in de HTML-download en in "Opslaan als PDF"._'

const opsomming = items => items.map(item => `- ${item}`).join('\n')
const sectie = (kop, ...blokken) => (blokken.some(Boolean) ? [`## ${kop}`, ...blokken.filter(Boolean)] : [])
const deel = (kop, items) => (items.length ? `### ${kop}\n\n${opsomming(items)}` : '')

// Haakjes en spaties in een adres breken de Markdown-link; gecodeerd blijft het hetzelfde adres.
const linkAdres = url => url.replace(/[()\s<>]/g, teken => `%${teken.charCodeAt(0).toString(16).toUpperCase().padStart(2, '0')}`)

function definitieRegels({ begrip, delen }) {
  const kop = begrip ? `**${begrip}**` : ''
  if (delen.length === 1) return `- ${[kop, delen[0]].filter(Boolean).join(': ')}`
  return [`- ${kop}`, ...delen.map(d => `  - ${d}`)].join('\n')
}

function bronMarkdown({ regel, url, linkTekst }) {
  const link = url ? `[${linkTekst || 'Bekijk de bron'}](${linkAdres(url)})` : ''
  return [regel, link].filter(Boolean).join(' · ')
}

function visualisatieMarkdown(v, i) {
  return [`### ${v.titel || `Visualisatie ${i + 1}`}`, GRAFIEK_REGEL, v.noot, bronMarkdown(v.bron), v.toelichting]
    .filter(Boolean).join('\n\n')
}

export function rapportMarkdown(rapport) {
  const r = rapport
  const blokken = [
    `# ${r.title || 'Rapport'}`,
    [...r.meta, r.instelling && `Instelling: ${r.instelling}`].filter(Boolean).join(' · '),
    ...sectie('Afwijking van je vraag', opsomming(r.afwijkingen)),
    ...sectie('Onderzoeksvraag', r.onderzoeksvraag),
    ...sectie('Reikwijdte', deel('Wat dit rapport wel beantwoordt', r.beantwoordt), deel('Wat dit rapport niet beantwoordt', r.beantwoordtNiet)),
    ...sectie('Gekozen definities', r.definities.map(definitieRegels).join('\n')),
    ...sectie('Visualisaties', ...r.visualisaties.map(visualisatieMarkdown)),
    ...sectie('Conclusie', r.conclusie),
    ...sectie('Bronnen', r.bronnen.map((b, i) => `${i + 1}. ${b}`).join('\n')),
    ...sectie('Herkomst', ...r.herkomst),
  ]
  return blokken.filter(Boolean).join('\n\n') + '\n'
}
