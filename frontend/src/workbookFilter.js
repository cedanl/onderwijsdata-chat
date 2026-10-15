// Title search in the report gallery (#562): with tens of reports the user types a few words
// instead of scrolling. Case and accents do not count ("economie" finds "Economië").
export function filterWorkbooks(workbooks, query) {
  const words = fold(query).split(/\s+/).filter(Boolean)
  if (words.length === 0) return workbooks
  return workbooks.filter(wb => {
    const title = typeof wb?.title === 'string' ? fold(wb.title) : ''
    return words.every(word => title.includes(word))
  })
}

function fold(text) {
  return String(text ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
}
