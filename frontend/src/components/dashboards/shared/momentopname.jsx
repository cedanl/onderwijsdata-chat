// De UWV-vacatures zijn een momentopname (#900): elk onderdeel dat ze gebruikt, noemt de peildatum uit de payload,
// niet een vaste maand. De arbeidsmarktmatch zegt daarbij wat haar labels betekenen en wat ze niet zeggen; de drempel,
// de jaren en de herkomst van de sectorindeling komen uit `match_duiding` (data/dashboard.py, _match_duiding).

const DATUM = new Intl.DateTimeFormat('nl-NL', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' })

// "2023-05-16" → "16 mei 2023"; meer peildata (komma's, zoals de server ze geeft) elk; iets anders ongewijzigd.
export function peildatumTekst(peildatum) {
  if (!peildatum) return null
  return String(peildatum).split(',').map(d => {
    const iso = d.trim()
    return /^\d{4}-\d{2}-\d{2}$/.test(iso) ? DATUM.format(new Date(`${iso}T00:00:00Z`)) : iso
  }).join(', ')
}

function peildatumOfOnbekend(peildatum) {
  return peildatumTekst(peildatum) ? `peildatum ${peildatumTekst(peildatum)}` : 'peildatum onbekend'
}

// "UWV Open Match, peildatum 16 mei 2023": voor ondertitels die de vacatures noemen.
export function uwvBron(peildatum) {
  return `UWV Open Match, ${peildatumOfOnbekend(peildatum)}`
}

// [2023, 2024, 2025] → "2023 tot en met 2025"; één jaar is dat jaar; geen jaren is null.
export function jarenTekst(jaren) {
  if (!jaren?.length) return null
  return jaren.length === 1 ? String(jaren[0]) : `${jaren[0]} tot en met ${jaren[jaren.length - 1]}`
}

export function MomentopnameBanner({ peildatum }) {
  return (
    <div className="db-momentopname" role="note">
      Momentopname: vacatures van UWV Open Match, {peildatumOfOnbekend(peildatum)}. Geen historische reeks en geen
      actuele stand: gebruik als indicatie.
    </div>
  )
}

const getal = n => Number(n).toLocaleString('nl-NL')

// Onder de match-tegels: bron, peildatum, drempel, de drie labels en wat de score niet zegt.
export function MatchDuiding({ duiding }) {
  if (!duiding) return null
  const drempel = duiding.drempel != null ? getal(duiding.drempel) : null
  const jaren = jarenTekst(duiding.diplomajaren)
  const mapping = duiding.sectormapping || {}
  const mappingVersie = mapping.mapping_versie && mapping.mapping_versie !== 'onbekend' ? `, versie ${mapping.mapping_versie}` : ''
  return (
    <div className="db-match-duiding dashboard-noot" role="note">
      <p>
        Per sector het aandeel in de gerelateerde vacatures ({uwvBron(duiding.vacatures_peildatum)}) tegenover het
        aandeel in de gediplomeerden van deze instelling (DUO, {jaren ? `gemiddeld over de diplomajaren ${jaren}` : 'gemiddeld per jaar'}).
        Beide aandelen gelden binnen de sectoren van deze instelling.
      </p>
      {drempel && (
        <ul>
          <li><strong>Schaarste</strong>: het vacature-aandeel is meer dan {drempel} keer het diploma-aandeel.</li>
          <li><strong>Overaanbod</strong>: het diploma-aandeel is meer dan {drempel} keer het vacature-aandeel.</li>
          <li><strong>Evenwicht</strong>: geen van beide aandelen is meer dan {drempel} keer het andere.</li>
        </ul>
      )}
      <p>
        Wat de score niet zegt: de vacatures zijn een bevroren stand van één dag, de gediplomeerden een gemiddelde over
        meer jaren. UWV legt bij vacatures geen opleidingsniveau vast, dus een sector telt ook banen op een ander niveau
        mee. Welke beroepenclusters bij een sector horen, is een indeling van deze app
        ({mapping.herkomst || 'LLM-classificatie, niet van UWV'}{mappingVersie}).
      </p>
    </div>
  )
}
