// A report only makes sense once data was actually fetched or plotted;
// greetings, definitions and clarification questions don't qualify.
export function hasReportableAnswer(messages) {
  return messages.some(m =>
    m.role === 'assistant' && !m.isError &&
    (m.figures?.length > 0 || m.tools?.some(t => t.snippet))
  )
}
