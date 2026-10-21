// The steps that ran in a turn are its provenance (#398): taking an answer back must not
// take them with it. The withdrawn text stays too, marked as replaced, so the trace shows
// what was corrected and why the correction steps are there.

// The server withdrew the text (message_cancel): the card stays open for the rewrite.
// `naStap` is how many steps had run, so an export can mark which came after the correction.
export function withdrawText(msg, reden) {
  if (!msg.content?.trim()) return msg
  // De reden in gewone taal, van de controle die de versie introk (CH-01).
  const versie = { tekst: msg.content, naStap: msg.tools?.length || 0, ...(reden?.length && { reden }) }
  return { ...msg, content: '', vervangen: [...(msg.vervangen || []), versie] }
}

// The turn ended without an answer in this card (clarification, error): keep the steps,
// drop half-written text. A card with nothing to show is removed (null).
export function closeWithoutText(msg) {
  if (!msg.tools?.length && !msg.vervangen?.length) return null
  return { ...msg, content: '', done: true }
}

// An answer cut off between two model rounds (#652): the next round had moved what the model wrote into the
// reasoning card as interim text (#393), and on a phone that card is closed by then. Without text of its own the
// answer showed only the question, "Redenering" and the connection line. The last interim text is what the user saw
// being written, so it comes back as the partial text of the answer.
export function metDeeltekst(msg) {
  if (msg.content || !msg.tussentekst?.length) return msg
  return { ...msg, content: msg.tussentekst.at(-1), tussentekst: msg.tussentekst.slice(0, -1) }
}
