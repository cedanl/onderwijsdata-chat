// The whole conversation as one markdown audit file: question, answer, and per step
// the code that reproduces it (#366). The snippets start from the source, so they
// also say where each number came from. Failed steps and error messages are out by
// default: an audit file is about the answer, not about the retries on the way.
// Het notebook (#1247) is hetzelfde gesprek uit dezelfde blokken, met de code als cellen.
import { conversationTitle } from './conversationTitle'
import { meldingRegels, metBronnen } from './answerBlocks'
import { manifestRegels } from './manifestRegels'
import { VASTE_MAAT_UITLEG, vasteMaat, vasteMaatLabel, vastgelegdTekst } from './vasteMaat'

const failed = step => ['error', 'empty', 'buiten_scope'].includes(step.status)

// A failed step says what went wrong. A call the scope boundary refused (#640) is named by its
// outcome alone: "CBS data opgehaald (CBS-opvraag geweigerd ...)" would contradict itself.
function stepLabel(step) {
  if (!failed(step) || !step.statusLabel) return step.label
  return step.status === 'buiten_scope' ? step.statusLabel : `${step.label} (${step.statusLabel})`
}

// The steps that go into an export, numbered without a gap. Steps from index `correctie` on ran
// after a withdrawn answer (#398).
function stappen(tools, fouten, correctie = Infinity) {
  return (tools || [])
    .map((t, i) => ({ ...t, naCorrectie: i >= correctie }))
    .filter(t => fouten || !failed(t))
    .map((t, i) => ({ nummer: i + 1, label: `${stepLabel(t)}${t.naCorrectie ? ' (na de correctie)' : ''}`, snippet: t.snippet }))
}

function stepLines(tools, { snippets, fouten }, correctie) {
  return stappen(tools, fouten, correctie).flatMap(({ nummer, label, snippet }) =>
    snippets && snippet ? [`${nummer}. ${label}`, '', '```python', snippet, '```', ''] : [`${nummer}. ${label}`])
}

const telt = (msg, fouten) => !msg.isError || fouten

// What stands under an answer, the same in markdown and notebook; the steps follow apart.
function antwoordBlokken(msg) {
  const blocks = []
  for (const { tekst } of msg.vervangen || []) {
    blocks.push(['**Ingetrokken na controle:**', ...tekst.split('\n')].map(r => `> ${r}`).join('\n'))
  }
  // The sources come from the server, no longer from the model's text (#416).
  if (msg.content) blocks.push('### Antwoord', metBronnen(msg.content, msg.bronnen))
  // Dezelfde regels als de kopieerknop (#1257): "Let op" en "Wat is gecontroleerd" (#1260).
  for (const regel of meldingRegels(msg)) blocks.push(`> ${regel}`)
  // Only get_maat behind the answer (#1242): the label as under the answer, with what its disclosure says.
  const vm = vasteMaat(msg.vaste_maat)
  if (vm) {
    blocks.push([`**${vasteMaatLabel(vm)}**`, VASTE_MAAT_UITLEG, `Teldefinitie: ${vm.teldefinitie}`, vastgelegdTekst(vm)].join('\n\n'))
  }
  for (const fig of msg.figures || []) blocks.push(`_Grafiek: ${fig.label || 'zonder titel'}_`)
  // Where the answer came from (#713): the model and versions that made it, and the version of the data behind it.
  const herkomst = manifestRegels(msg.manifest)
  if (herkomst) {
    blocks.push('#### Herkomst', [
      `Verantwoording: ${herkomst.verantwoording}`,
      herkomst.dataversie && `Dataversie: ${herkomst.dataversie}`,
    ].filter(Boolean).join('\n\n'))
  }
  return blocks
}

function answerBlocks(msg, options) {
  if (!telt(msg, options.fouten)) return []
  const blocks = antwoordBlokken(msg)
  const steps = stepLines(msg.tools, options, msg.vervangen?.[0]?.naStap)
  if (steps.length) blocks.push('#### Stappen', steps.join('\n').trim())
  return blocks
}

const titel = messages => conversationTitle(messages.find(m => m.role === 'user')?.content)

// De bestandsnaam van een export: alleen letters, cijfers en _ uit de titel, niets anders uit het gesprek (#478).
export const exportBestandsnaam = (messages, extensie) => titel(messages).replace(/[^a-zA-Z0-9]/g, '_') + extensie

export function conversationMarkdown(messages, { snippets = true, fouten = false, datum }) {
  const blocks = [`# ${titel(messages)}`, `Geëxporteerd uit openEDUdata+ op ${datum}.`]
  let vraag = 0
  for (const msg of messages) {
    if (msg.role === 'user') blocks.push(`## Vraag ${++vraag}`, msg.content)
    else if (msg.role === 'assistant') blocks.push(...answerBlocks(msg, { snippets, fouten }))
  }
  return blocks.join('\n\n') + '\n'
}

// Letterlijk de zin van een codeverzoek over een stap zonder code (#969, agent/codeverzoek.py GEEN_CODE);
// tests/test_notebook_export.py houdt ze gelijk.
export const GEEN_CODE = 'voor die stap maakt de app geen code om zelf na te rekenen.'

// De versiekop van tools/pakketversies.versiekop: "# Gemaakt met …." en "# <opdracht>: pip install <pakketten>",
// met een lege regel ervoor de code begint.
const VERSIEKOP = /^(# Gemaakt met .*)\n# (.+?): pip install (.+)(?:\n\n?|$)/m

// One install cell for the whole notebook: the version header of the first snippet with one, and every package the
// snippets with that same header install (a chart adds plotly). Those snippets lose their header; a header of another
// version (a conversation that spans a deploy) stays in its own cell, so no line claims a version it was not made with.
function installatie(codes) {
  let kop
  const pakketten = []
  const zonderKop = codes.map(code => {
    const m = code.match(VERSIEKOP)
    if (!m || (kop && m[1] !== kop[1])) return code
    kop ??= m
    for (const p of m[3].match(/"[^"]*"|\S+/g)) if (!pakketten.includes(p)) pakketten.push(p)
    return code.replace(m[0], '')
  })
  return { cel: kop && [kop[1], `# ${kop[2]}:`, `%pip install ${pakketten.join(' ')}`].join('\n'), zonderKop }
}

// nbformat stores a cell's text as its lines, each but the last with its newline.
const regels = tekst => tekst.trimEnd().split('\n').map((r, i, a) => (i < a.length - 1 ? `${r}\n` : r))

// Het gesprek als Jupyter-notebook (nbformat 4.5, #1247): per beurt een markdowncel met vraag, antwoord en herkomst
// zoals in de markdownexport, dan per stap zijn snippet als codecel, bovenaan één cel die de pakketten installeert.
// De app voert niets uit; ids zijn de celindex, zodat dezelfde export hetzelfde bestand geeft.
export function conversationNotebook(messages, { fouten = false, datum }) {
  const cellen = [{ type: 'markdown', tekst: [
    `# ${titel(messages)}`,
    `Geëxporteerd uit openEDUdata+ op ${datum}.`,
    'Draai de cellen van boven naar beneden. Een bron kan sinds de export nieuwe of herziene cijfers hebben; ' +
      'de herkomst onder elk antwoord noemt de dataversie waarmee de app rekende.',
  ].join('\n\n') }]
  let vraag = []
  let vragen = 0
  for (const msg of messages) {
    if (msg.role === 'user') vraag.push(`## Vraag ${++vragen}`, msg.content)
    if (msg.role !== 'assistant' || !telt(msg, fouten)) continue
    const blokken = [...vraag, ...antwoordBlokken(msg)]
    vraag = []
    if (blokken.length) cellen.push({ type: 'markdown', tekst: blokken.join('\n\n') })
    for (const { nummer, label, snippet } of stappen(msg.tools, fouten, msg.vervangen?.[0]?.naStap)) {
      cellen.push(snippet
        ? { type: 'code', kop: `# Stap ${nummer}: ${label.replace(/\s+/g, ' ')}`, tekst: snippet }
        : { type: 'markdown', tekst: `Stap ${nummer}, "${label}", heeft geen code: ${GEEN_CODE}` })
    }
  }
  if (vraag.length) cellen.push({ type: 'markdown', tekst: vraag.join('\n\n') })

  const code = cellen.filter(c => c.type === 'code')
  const { cel, zonderKop } = installatie(code.map(c => c.tekst))
  code.forEach((c, i) => { c.tekst = `${c.kop}\n${zonderKop[i]}` })
  if (cel) cellen.splice(1, 0, { type: 'code', tekst: cel })

  return {
    nbformat: 4,
    nbformat_minor: 5,
    metadata: {
      kernelspec: { name: 'python3', display_name: 'Python 3', language: 'python' },
      language_info: { name: 'python' },
    },
    cells: cellen.map(({ type, tekst }, i) => ({
      cell_type: type,
      id: `cel-${i}`,
      metadata: {},
      source: regels(tekst),
      ...(type === 'code' && { execution_count: null, outputs: [] }),
    })),
  }
}
