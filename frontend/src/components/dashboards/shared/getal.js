// Eén Nederlandse notatie voor elk getal op de dashboards (#904): tegels, tabellen, tooltips en assen. Komma als
// decimaalteken, punt als duizendtal: 52,3 en 12.345. Zonder waarde een streepje.
export function fmt(n) {
  if (n == null) return '—'
  return Number(n).toLocaleString('nl-NL')
}
