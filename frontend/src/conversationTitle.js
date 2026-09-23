const MAX_TITLE_LENGTH = 80

// The first user message becomes the title; strip markup so the sidebar
// shows readable text rather than literal tags.
export function conversationTitle(text) {
  const plain = String(text ?? '').replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim()
  return plain.slice(0, MAX_TITLE_LENGTH) || 'Nieuw gesprek'
}
