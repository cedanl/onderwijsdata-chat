import { useEffect, useId, useRef, useState } from 'react'
import { useNavigate, useLocation, useSearchParams } from 'react-router-dom'
import { DEFAULT_INSTELLING } from '../constants'
import WorkbookViewer from '../components/WorkbookViewer'
import ConfirmModal from '../components/ConfirmModal'
import FeedbackLink from '../components/FeedbackLink'
import WorkbookPreview from '../components/WorkbookPreviews'
import { useWorkbookGallery } from '../hooks/useWorkbookGallery'
import { useDocumentTitle, pageTitle } from '../hooks/useDocumentTitle'
import { groupByMonth } from '../workbookGroups'
import { filterWorkbooks } from '../workbookFilter'
import { inVolgorde, noteerRapport, useRecent, wisselFavoriet } from '../recentBekeken'

function formatDate(iso) {
  return new Date(iso).toLocaleDateString('nl-NL', { day: 'numeric', month: 'short', year: 'numeric' })
}

// A star to mark a favourite (#603): kept in this browser only, like "recent bekeken".
function FavorietKnop({ wb, aan }) {
  return (
    <button type="button"
      className={`wb-fav-btn${aan ? ' aan' : ''}`}
      aria-pressed={aan}
      aria-label={`Favoriet: ${wb.title}`}
      title={aan ? 'Uit je favorieten halen' : 'Markeer als favoriet'}
      onClick={e => { e.preventDefault(); e.stopPropagation(); wisselFavoriet(wb.id) }}
    >
      <svg viewBox="0 0 24 24" fill={aan ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
      </svg>
    </button>
  )
}

// One row of reports to go back to quickly (#603): favourites or recently viewed, as small buttons.
function SnelRij({ kop, rapporten, onOpen }) {
  if (!rapporten.length) return null
  return (
    <div className="wb-snel-rij">
      <h2 className="wb-snel-kop">{kop}</h2>
      <div className="wb-snel-knoppen">
        {rapporten.map(wb => (
          <button key={wb.id} type="button" className="wb-snel-knop" onClick={() => onOpen(wb)}>{wb.title}</button>
        ))}
      </div>
    </div>
  )
}

function RapportCard({ wb, onOpen, onDelete, mode, favoriet = false }) {
  return (
    <a
      href={`/rapporten?id=${encodeURIComponent(wb.id)}`}
      className="wb-card"
      onClick={e => { e.preventDefault(); onOpen() }}
    >
      <div className="wb-card-thumb">
        <WorkbookPreview wb={wb} mode={mode} />
      </div>
      <div className="wb-card-body">
        <div className="wb-card-title">{wb.title}</div>
        <div className="wb-card-desc">{wb.description}</div>
        <div className="wb-card-footer">
          <span className="wb-card-date">{formatDate(wb.createdAt)}</span>
          <FavorietKnop wb={wb} aan={favoriet} />
          <button type="button"
            className="wb-delete-btn"
            title="Verwijder"
            aria-label={`Verwijder rapport ${wb.title}`}
            onClick={e => { e.preventDefault(); e.stopPropagation(); onDelete() }}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="3 6 5 6 21 6" /><path d="M19 6l-1 14H6L5 6" /><path d="M10 11v6" /><path d="M14 11v6" /><path d="M9 6V4h6v2" />
            </svg>
          </button>
        </div>
      </div>
    </a>
  )
}

// Title search (#562): filters the list already in the browser on every keystroke.
function RapportenZoekveld({ query, onChange, inputRef }) {
  const id = useId()
  return (
    <div className="wb-gallery-search">
      <label htmlFor={id} className="wb-gallery-search-label">Zoek in rapporten</label>
      <input
        id={id}
        ref={inputRef}
        type="search"
        className="wb-gallery-search-input"
        placeholder="Titel of woorden uit de titel"
        autoComplete="off"
        value={query}
        onChange={e => onChange(e.target.value)}
      />
    </div>
  )
}

// Never a blank page: no hits says so and offers the way back to the full list.
function GeenTreffers({ query, onClear }) {
  return (
    <div className="wb-gallery-no-hits">
      <p>Geen rapporten gevonden voor {`'${query}'`}</p>
      <button type="button" className="wb-gallery-clear-btn" onClick={onClear}>Wis zoekopdracht</button>
    </div>
  )
}

function aantalTekst(zichtbaar, totaal, zoekt) {
  const rapport = `rapport${totaal !== 1 ? 'en' : ''}`
  return zoekt ? `${zichtbaar} van ${totaal} ${rapport}` : `${totaal} ${rapport}`
}

export default function RapportenPage({ settings, feedbackEnabled = false }) {
  const mode = settings?.mode || 'system'
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams, setSearchParams] = useSearchParams()
  const pendingId = searchParams.get('id')
  // Workbook passed via navigation state (from chat → rapport generation); avoids
  // setSearchParams/History API calls that can hit Firefox's rate limit.
  const navWorkbook = location.state?.pendingWorkbook ?? null

  const { workbooks: rapporten, loading, missingId, openFout, opening, selected, setSelected, pendingConfirm, setPendingConfirm, handleUpdate, handleDelete } =
    useWorkbookGallery({
      type: 'report',
      pendingId: navWorkbook ? null : pendingId,
      clearPending: undefined,
      deleteMessage: 'Weet je zeker dat je dit rapport wilt verwijderen?',
      initialSelected: navWorkbook,
    })
  useDocumentTitle(pageTitle(selected?.title || 'Rapporten'))
  const [query, setQuery] = useState('')
  const searchRef = useRef(null)
  const zichtbaar = filterWorkbooks(rapporten, query)
  const zoekt = query.trim() !== ''
  const recent = useRecent()
  const favorieten = inVolgorde(recent.favorieten, rapporten)
  const recentBekeken = inVolgorde(recent.rapporten, rapporten).slice(0, 4)
  const openRapport = wb => { setSelected(wb); setSearchParams({ id: wb.id }, { replace: true }) }

  // An opened report counts as viewed in this browser (#603).
  useEffect(() => { if (selected?.id) noteerRapport(selected.id) }, [selected?.id])

  useEffect(() => {
    if (!selected && !opening && pendingId && (missingId === pendingId || openFout)) {
      setSearchParams({}, { replace: true })
    }
  }, [selected, opening, pendingId, missingId, openFout, setSearchParams])

  const instelling = settings?.instelling?.trim() || DEFAULT_INSTELLING

  if (selected) {
    return (
      <WorkbookViewer
        workbook={selected}
        instelling={instelling}
        onBack={() => { setSelected(null); setSearchParams({}, { replace: true }) }}
        onUpdate={handleUpdate}
        backLabel="Rapporten"
        feedbackEnabled={feedbackEnabled}
        mode={mode}
      />
    )
  }

  if (opening || (pendingId && !navWorkbook && missingId !== pendingId && !openFout)) {
    return (
      <div className="wb-gallery-page">
        <div className="wb-gallery-loading" aria-busy="true" role="status">
          <span className="spinner" aria-hidden="true" />
          Rapport wordt opgehaald…
        </div>
      </div>
    )
  }

  return (
    <>
      {pendingConfirm && (
        <ConfirmModal
          message={pendingConfirm.message}
          onConfirm={() => { pendingConfirm.onConfirm(); setPendingConfirm(null) }}
          onCancel={() => setPendingConfirm(null)}
        />
      )}
      <div className="wb-gallery-page">
        <div className="wb-gallery-header">
          <div>
            <h1 className="wb-gallery-title">Rapporten</h1>
            {/* A live region only during a search: a screen reader hears the number of hits while the user
                types, but not the total once when the list loads. */}
            <div className="wb-gallery-sub" role={zoekt ? 'status' : undefined}>
              {loading && rapporten.length === 0 ? '' : aantalTekst(zichtbaar.length, rapporten.length, zoekt)}
            </div>
          </div>
        </div>

        {rapporten.length > 0 && <RapportenZoekveld query={query} onChange={setQuery} inputRef={searchRef} />}

        {/* Back to what you use (#603), only in this browser: in a shared account others do not see it. */}
        {!zoekt && (favorieten.length > 0 || recentBekeken.length > 0) && (
          <section className="wb-snel" aria-label="Snel terug">
            <SnelRij kop="Favorieten" rapporten={favorieten} onOpen={openRapport} />
            <SnelRij kop="Recent bekeken" rapporten={recentBekeken} onOpen={openRapport} />
            <p className="wb-snel-noot">Alleen in deze browser: anderen met hetzelfde account zien dit niet.</p>
          </section>
        )}

        {missingId && (
          <div className="wb-gallery-notice" role="alert">
            Dit rapport is niet gevonden. Het is misschien verwijderd of opgeslagen onder een ander account.
          </div>
        )}
        {openFout && !missingId && <div className="wb-gallery-notice" role="alert">{openFout}</div>}

        {loading && rapporten.length === 0 ? (
          <div className="wb-gallery-loading" aria-busy="true" role="status">
            <span className="spinner" aria-hidden="true" />
            Rapporten laden…
          </div>
        ) : rapporten.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '64px 24px', color: 'var(--gray-500)' }}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ width: 48, height: 48, margin: '0 auto 16px', display: 'block', opacity: .4 }}>
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" />
            </svg>
            <p style={{ marginBottom: 16, fontSize: '.95rem' }}>Nog geen rapporten opgeslagen.</p>
            <button type="button" className="navbar-cta" onClick={() => navigate('/chat')}>
              Ga naar Chat
            </button>
            <p style={{ marginTop: 12, fontSize: '.82rem', color: 'var(--muted-text)' }}>
              Stel een vraag en klik op &ldquo;Genereer rapport&rdquo; om een rapport hier op te slaan.
            </p>
          </div>
        ) : zichtbaar.length === 0 ? (
          <GeenTreffers query={query.trim()} onClear={() => { setQuery(''); searchRef.current?.focus() }} />
        ) : (
          groupByMonth(zichtbaar).map(groep => (
            <section key={groep.label} className="wb-gallery-group">
              <h2 className="wb-gallery-group-title">{groep.label} <span>({groep.workbooks.length})</span></h2>
              <div className="wb-grid">
                {groep.workbooks.map(wb => (
                  <RapportCard mode={mode}
                    key={wb.id}
                    wb={wb}
                    favoriet={recent.favorieten.includes(String(wb.id))}
                    onOpen={() => openRapport(wb)}
                    onDelete={() => handleDelete(wb.id)}
                  />
                ))}
              </div>
            </section>
          ))
        )}
        {/* /rapporten has no footer: the general feedback form (#600) gets one line at the bottom. */}
        {feedbackEnabled && (
          <p className="wb-gallery-feedback">
            Mis je iets of werkt iets niet? <FeedbackLink>Geef feedback</FeedbackLink>
          </p>
        )}
      </div>
    </>
  )
}
