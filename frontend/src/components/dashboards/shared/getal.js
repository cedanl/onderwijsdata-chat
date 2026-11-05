// Eén Nederlandse notatie voor elk getal op de dashboards (#904): tegels, tabellen, tooltips en assen. Komma als
// decimaalteken, punt als duizendtal: 52,3 en 12.345. Zonder waarde een streepje.
export function fmt(n) {
  if (n == null) return '—'
  return Number(n).toLocaleString('nl-NL')
}

// Een percentage met een vast aantal decimalen, zodat 32,0% naast 67,2% staat en niet 32% naast 67,2% (#951).
export function fmtProcent(n, decimalen = 1) {
  if (n == null) return '—'
  return Number(n).toLocaleString('nl-NL', { minimumFractionDigits: decimalen, maximumFractionDigits: decimalen })
}
