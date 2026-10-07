// The report gallery grows to over a hundred cards (#427): grouped by the month they were
// made, newest first, a user finds last week's report without scrolling the whole list.
export function groupByMonth(workbooks) {
  const sorted = [...workbooks].sort((a, b) => String(b.createdAt).localeCompare(String(a.createdAt)))
  const groups = []
  for (const wb of sorted) {
    const label = monthLabel(wb.createdAt)
    const last = groups.at(-1)
    if (last?.label === label) last.workbooks.push(wb)
    else groups.push({ label, workbooks: [wb] })
  }
  return groups
}

function monthLabel(iso) {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return 'Zonder datum'
  const label = date.toLocaleDateString('nl-NL', { month: 'long', year: 'numeric' })
  return label.charAt(0).toUpperCase() + label.slice(1)
}
