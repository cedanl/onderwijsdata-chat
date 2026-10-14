// What became of a clarification card, read from the conversation itself (#109): the first
// question after the card answers it, whether an option was clicked or something was typed.
// Kept in component state, the choice was lost on every reload.
export function clarificationAnswer(messages, index) {
  const next = messages.slice(index + 1).find(m => m.role === 'user')
  return next ? { answered: true, choice: next.content } : { answered: false, choice: null }
}

export function hasOpenClarification(messages) {
  return !!messages.at(-1)?.clarification
}

// The question a clarification card asks about (#494), for "Anders formuleren": the nearest earlier
// question with text. A click on the card right before it is a choice, not a question, so a chain
// of cards leads back to the question that started it; a typed answer does count. Null if none.
export function originalQuestion(messages, index) {
  const j = messages.slice(0, index).findLastIndex(isQuestion)
  if (j < 0) return null
  const { content } = messages[j]
  return isChoiceOn(messages[j - 1], content) ? originalQuestion(messages, j - 1) : content
}

const isQuestion = m => m.role === 'user' && !m.isError && typeof m.content === 'string' && !!m.content.trim()

const optionLabel = opt => (typeof opt === 'string' ? opt : opt?.label)

function isChoiceOn(card, content) {
  return Array.isArray(card?.clarification) && card.clarification.some(opt => optionLabel(opt) === content)
}
