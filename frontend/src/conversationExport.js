// The whole conversation as one markdown audit file: question, answer, and per step
// the code that reproduces it (#366). The snippets start from the source, so they
// also say where each number came from. Failed steps and error messages are out by
// default: an audit file is about the answer, not about the retries on the way.
import { conversationTitle } from './conversationTitle'
import { metBronnen } from './answerBlocks'

const failed = step => step.status === 'error' || step.status === 'empty'

// Steps from index `correctie` on ran after a withdrawn answer (#398).
function stepLines(tools, { snippets, fouten }, correctie = Infinity) {
  const steps = (tools || []).map((t, i) => ({ ...t, naCorrectie: i >= correctie })).filter(t => fouten || !failed(t))
  return steps.flatMap((t, i) => {
    const label = failed(t) && t.statusLabel ? `${t.label} (${t.statusLabel})` : t.label
    const lines = [`${i + 1}. ${label}${t.naCorrectie ? ' (na de correctie)' : ''}`]
    if (snippets && t.snippet) lines.push('', '```python', t.snippet, '```', '')
    return lines
  })
}

function answerBlocks(msg, options) {
  if (msg.isError && !options.fouten) return []
  const blocks = []
  for (const { tekst } of msg.vervangen || []) {
    blocks.push(['**Ingetrokken na controle:**', ...tekst.split('\n')].map(r => `> ${r}`).join('\n'))
  }
  // The sources come from the server, no longer from the model's text (#416).
  if (msg.content) blocks.push('### Antwoord', metBronnen(msg.content, msg.bronnen))
  for (const zin of msg.controle || []) blocks.push(`> Let op: ${zin}`)
  for (const fig of msg.figures || []) blocks.push(`_Grafiek: ${fig.label || 'zonder titel'}_`)
  const steps = stepLines(msg.tools, options, msg.vervangen?.[0]?.naStap)
  if (steps.length) blocks.push('#### Stappen', steps.join('\n').trim())
  return blocks
}

export function conversationMarkdown(messages, { snippets = true, fouten = false, datum }) {
  const firstQuestion = messages.find(m => m.role === 'user')
  const blocks = [`# ${conversationTitle(firstQuestion?.content)}`, `Geëxporteerd uit EDUdata op ${datum}.`]
  let vraag = 0
  for (const msg of messages) {
    if (msg.role === 'user') blocks.push(`## Vraag ${++vraag}`, msg.content)
    else if (msg.role === 'assistant') blocks.push(...answerBlocks(msg, { snippets, fouten }))
  }
  return blocks.join('\n\n') + '\n'
}
