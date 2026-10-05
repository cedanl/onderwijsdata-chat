// The whole conversation as one markdown audit file: question, answer, and per step
// the code that reproduces it (#366). The snippets start from the source, so they
// also say where each number came from. Failed steps and error messages are out by
// default: an audit file is about the answer, not about the retries on the way.
import { conversationTitle } from './conversationTitle'

const failed = step => step.status === 'error' || step.status === 'empty'

function stepLines(tools, { snippets, fouten }) {
  const steps = (tools || []).filter(t => fouten || !failed(t))
  return steps.flatMap((t, i) => {
    const label = failed(t) && t.statusLabel ? `${t.label} (${t.statusLabel})` : t.label
    const lines = [`${i + 1}. ${label}`]
    if (snippets && t.snippet) lines.push('', '```python', t.snippet, '```', '')
    return lines
  })
}

function answerBlocks(msg, options) {
  if (msg.isError && !options.fouten) return []
  const blocks = []
  if (msg.content) blocks.push('### Antwoord', msg.content)
  for (const zin of msg.controle || []) blocks.push(`> Let op: ${zin}`)
  for (const fig of msg.figures || []) blocks.push(`_Grafiek: ${fig.label || 'zonder titel'}_`)
  const steps = stepLines(msg.tools, options)
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
