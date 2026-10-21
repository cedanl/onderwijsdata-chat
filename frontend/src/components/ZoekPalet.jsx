/* eslint-disable jsx-a11y/no-noninteractive-element-interactions, jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions */
import { useEffect, useId, useState } from 'react'
import { createPortal } from 'react-dom'
import { useDialog } from '../hooks/useDialog'
import { useConversationSearch } from '../hooks/useConversationSearch'
import { getWorkbooks, getWorkbookType, loadWorkbooksFromServer } from '../workbooks'
import { filterWorkbooks } from '../workbookFilter'
import { relatieveDatumTijd } from '../relatieveDatum'

// At most this many hits per group: the palette is for jumping, the pages are for browsing.
const PER_GROEP = 6

function rapportenVan(workbooks) {
  return workbooks.filter(wb => getWorkbookType(wb) === 'report')
}

function rapportDatum(wb) {
  const ms = Date.parse(wb.createdAt ?? wb.created_at ?? '')
  return Number.isNaN(ms) ? '' : relatieveDatumTijd(ms)
}

// One search over conversations and reports (#602), with the search logic each page already has: the
// server searches conversation titles and text (#124), the browser filters report titles (#562). Opened
// with Ctrl/⌘K or the search button in the header. Arrow keys move through the hits, Enter opens one.
export default function ZoekPalet({ onClose, onOpenGesprek, onOpenRapport }) {
  const dialogRef = useDialog(onClose)
  const id = useId()
  const gesprekken = useConversationSearch()
  const [rapporten, setRapporten] = useState(() => rapportenVan(getWorkbooks()))
  const [actief, setActief] = useState(0)

  useEffect(() => {
    let weg = false
    loadWorkbooksFromServer().then(wbs => { if (!weg) setRapporten(rapportenVan(wbs)) }).catch(() => {})
    return () => { weg = true }
  }, [])

  const term = gesprekken.query.trim()
  const treffers = term ? [
    ...(gesprekken.results ?? []).slice(0, PER_GROEP).map(c => ({
      soort: 'gesprek', key: `g-${c.id}`, titel: c.title || 'Gesprek zonder titel', datum: relatieveDatumTijd(c.timestamp),
      open: () => onOpenGesprek(String(c.id)),
    })),
    ...filterWorkbooks(rapporten, term).slice(0, PER_GROEP).map(wb => ({
      soort: 'rapport', key: `r-${wb.id}`, titel: wb.title || 'Rapport zonder titel', datum: rapportDatum(wb),
      open: () => onOpenRapport(String(wb.id)),
    })),
  ] : []
  const gekozen = Math.min(actief, Math.max(treffers.length - 1, 0))

  let status = ''
  if (!term) status = 'Typ om te zoeken in je gesprekken (titel en tekst) en rapporten (titel).'
  else if (gesprekken.error) status = 'Gesprekken zoeken lukt nu niet. Rapporten staan hieronder.'
  else if (gesprekken.searching && !gesprekken.results) status = 'Zoeken…'
  else status = treffers.length ? `${treffers.length} ${treffers.length === 1 ? 'treffer' : 'treffers'}` : 'Niets gevonden'

  function onKeyDown(e) {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault()
      if (!treffers.length) return
      const stap = e.key === 'ArrowDown' ? 1 : -1
      setActief((gekozen + stap + treffers.length) % treffers.length)
    } else if (e.key === 'Enter' && treffers[gekozen]) {
      e.preventDefault()
      treffers[gekozen].open()
    }
  }

  const optieId = i => `${id}-optie-${i}`
  const groep = (soort, kop) => {
    const items = treffers.map((t, i) => [t, i]).filter(([t]) => t.soort === soort)
    if (!items.length) return null
    return (
      <div role="group" aria-labelledby={`${id}-${soort}`} className="zoek-groep">
        <div id={`${id}-${soort}`} className="zoek-groep-kop">{kop}</div>
        {items.map(([t, i]) => (
          <div key={t.key} id={optieId(i)} role="option" aria-selected={i === gekozen} tabIndex={-1}
            className={`zoek-optie${i === gekozen ? ' actief' : ''}`}
            onMouseMove={() => setActief(i)} onClick={t.open}>
            <span className="zoek-optie-titel">{t.titel}</span>
            {t.datum && <span className="zoek-optie-datum">{t.datum}</span>}
          </div>
        ))}
      </div>
    )
  }

  const closeFromBackdrop = e => {
    e.stopPropagation()
    onClose()
  }

  return createPortal(
    <div className="modal-overlay zoek-overlay" onClick={closeFromBackdrop}>
      <div className="zoek-palet" ref={dialogRef} role="dialog" aria-modal="true" aria-label="Zoeken" tabIndex={-1}
        onClick={e => e.stopPropagation()}>
        <div className="zoek-invoerrij">
          <svg className="zoek-icoon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" />
          </svg>
          <input
            type="search"
            className="zoek-invoer"
            role="combobox"
            aria-expanded={treffers.length > 0}
            aria-controls={`${id}-lijst`}
            aria-activedescendant={treffers.length ? optieId(gekozen) : undefined}
            aria-autocomplete="list"
            aria-label="Zoek in gesprekken en rapporten"
            placeholder="Zoek in gesprekken en rapporten"
            value={gesprekken.query}
            onChange={e => { gesprekken.setQuery(e.target.value); setActief(0) }}
            onKeyDown={onKeyDown}
          />
          <kbd className="zoek-toets zoek-toets-esc" aria-hidden="true">Esc</kbd>
        </div>
        <div id={`${id}-lijst`} role="listbox" aria-label="Treffers" className="zoek-lijst">
          {groep('gesprek', 'Gesprekken')}
          {groep('rapport', 'Rapporten')}
        </div>
        <div className="zoek-voet">
          <p className="zoek-status" role="status">{status}</p>
          <span className="zoek-hints" aria-hidden="true"><span>↑↓ kiezen</span><span>↵ openen</span></span>
        </div>
      </div>
    </div>,
    document.body,
  )
}
