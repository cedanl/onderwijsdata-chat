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
