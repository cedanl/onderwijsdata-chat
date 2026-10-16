import { useState, useCallback, useEffect, useRef } from 'react'
import { refreshDashboard as refreshDashboardApi, fetchFeedbackGiven } from '../api'
import { useReportFrame } from '../hooks/useReportFrame'
import { useMediaQuery, NARROW_SCREEN } from '../hooks/useMediaQuery'
import { updateWorkbook, BUILTIN_MIJN_INSTELLING, BUILTIN_ARBEIDSMARKT, BUILTIN_NATIONAAL } from '../workbooks'
import { InlineDashboardMijnInstelling, InlineDashboardArbeidsmarkt, InlineDashboardNationaal } from './InlineDashboards'
import GeneratedDashboard from './GeneratedDashboard'
import FeedbackModal from './FeedbackModal'
import WorkbookDownload from './WorkbookDownload'
import RapportNavActies from './RapportNavActies'
import ReportFrameFallback from './ReportFrameFallback'

const BUILTIN_COMPONENTS = {
  [BUILTIN_MIJN_INSTELLING.id]: InlineDashboardMijnInstelling,
  [BUILTIN_ARBEIDSMARKT.id]: InlineDashboardArbeidsmarkt,
  [BUILTIN_NATIONAAL.id]: InlineDashboardNationaal,
}

// save: the download target, for tests (as in WorkbookDownload). mode: the app's theme choice, which the report
// frame follows (#568).
export default function WorkbookViewer({ workbook, instelling, onBack, onUpdate, backLabel = 'Dashboards', feedbackEnabled = false, save, mode }) {
  const [refreshing, setRefreshing] = useState(false) // false of de lopende modus: 'ververs' | 'reproduceer'
  const [refreshError, setRefreshError] = useState(null)
  const [refreshResult, setRefreshResult] = useState(null) // { melding, veranderingen } van de laatste herhaling
  const [saveError, setSaveError] = useState(null)
  const [editingTitle, setEditingTitle] = useState(false)
  const [titleDraft, setTitleDraft] = useState('')
  const titleInputRef = useRef(null)
  const [showFeedback, setShowFeedback] = useState(false)
  const [feedbackThanks, setFeedbackThanks] = useState(false)
  const [feedbackGiven, setFeedbackGiven] = useState(false)

  useEffect(() => {
    setFeedbackGiven(false)
    if (!feedbackEnabled) return
    let cancelled = false
    fetchFeedbackGiven()
      .then(ids => { if (!cancelled) setFeedbackGiven(ids.includes(workbook.id)) })
      .catch(() => { /* status is cosmetic; the button still works */ })
    return () => { cancelled = true }
  }, [feedbackEnabled, workbook.id])

  useEffect(() => {
    if (!feedbackThanks) return
    const timer = setTimeout(() => setFeedbackThanks(false), 4000)
    return () => clearTimeout(timer)
  }, [feedbackThanks])

  const handleRefresh = useCallback(async (mode = 'ververs') => {
    const spec = workbook?.dashboardSpec
    if (refreshing || (!spec?.figure_recipes?.length && !spec?.recipe?.length)) return
    setRefreshing(mode)
    setRefreshError(null)
    setRefreshResult(null)
    try {
      const { spec: freshSpec, melding, veranderingen } = await refreshDashboardApi(spec, { instelling }, mode)
      setRefreshResult({ melding, veranderingen: veranderingen || [] })
      if (mode === 'ververs') {
        // Reproduceren verandert de data niet; alleen een verversing is het bewaren waard.
        onUpdate(await updateWorkbook(workbook, { dashboardSpec: freshSpec }))
      }
    } catch (err) {
      setRefreshError(err.message || 'Herhalen mislukt')
    } finally {
      setRefreshing(false)
    }
  }, [workbook, instelling, refreshing, onUpdate])

  const handleTitleEdit = useCallback(() => {
    if (workbook.builtin) return
    setTitleDraft(workbook.title)
    setEditingTitle(true)
    setTimeout(() => titleInputRef.current?.focus(), 0)
  }, [workbook])

  const handleTitleSave = useCallback(() => {
    const trimmed = titleDraft.trim()
    if (!trimmed || trimmed === workbook.title) {
      setEditingTitle(false)
      return
    }
    setEditingTitle(false)
    setSaveError(null)
    onUpdate({ ...workbook, title: trimmed })
    updateWorkbook(workbook, { title: trimmed }).catch(err => {
      onUpdate(workbook)
      setSaveError(`Titel niet opgeslagen: ${err.message}`)
    })
  }, [workbook, titleDraft, onUpdate])

  const spec = workbook.dashboardSpec
  const canRefresh = spec && (spec.figure_recipes?.length || spec.recipe?.length)
  const BuiltinDash = BUILTIN_COMPONENTS[workbook.id]
  // Op een telefoon is er geen ruimte voor titel én knoppen naast elkaar (#604): de titel blijft op één
  // regel en Download en feedback verhuizen naar het ⋯-menu in de navbar, net als bij de chat (#596).
  // Desktop houdt de knoppen inline in de kopbalk.
  const smal = useMediaQuery(NARROW_SCREEN)
  // A report renders in a sandboxed frame whose content is not in this DOM: until it has loaded the region is
  // busy, a report without content says so instead of showing a blank frame (#387, #533), and a frame that
  // shows nothing gets a notice with the download outside it (#541).
  const isReport = !BuiltinDash && !spec
  const reportEmpty = isReport && !String(workbook.htmlContent ?? '').trim()
  const reportFrame = useReportFrame(isReport && !reportEmpty ? workbook.htmlContent : null, mode)

  return (
    <div className="wb-viewer">
      <div className="wb-viewer-bar">
        <button type="button" className="wb-back-btn" onClick={onBack}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="15 18 9 12 15 6" />
          </svg>
          {backLabel}
        </button>
        <h1 className="wb-viewer-heading">
          {editingTitle ? (
            <input
              ref={titleInputRef}
              className="wb-viewer-title title-edit-input"
              value={titleDraft}
              onChange={e => setTitleDraft(e.target.value)}
              onBlur={handleTitleSave}
              onKeyDown={e => { if (e.key === 'Enter') handleTitleSave(); if (e.key === 'Escape') setEditingTitle(false) }}
            />
          ) : (
            <span
              className="wb-viewer-title"
              role={workbook.builtin ? undefined : "button"}
              tabIndex={workbook.builtin ? undefined : 0}
              onClick={handleTitleEdit}
              onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleTitleEdit() } }}
              style={{ cursor: workbook.builtin ? 'default' : 'pointer' }}
              title={workbook.builtin ? undefined : 'Klik om titel te bewerken'}
            >
              {workbook.title}
              {!workbook.builtin && (
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 14, height: 14, opacity: 0.4, flexShrink: 0 }}>
                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                  <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                </svg>
              )}
            </span>
          )}
        </h1>
        {smal ? (
          <RapportNavActies
            workbook={workbook} instelling={instelling} save={save}
            feedbackEnabled={feedbackEnabled} feedbackGiven={feedbackGiven}
            onFeedback={() => setShowFeedback(true)}
          />
        ) : (
          <div className="wb-viewer-actions">
            <WorkbookDownload workbook={workbook} instelling={instelling} save={save} />
            {feedbackEnabled && (
              feedbackGiven ? (
                <span className="wb-feedback-given" role="status">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                  Feedback gegeven
                </span>
              ) : (
                <button type="button" className="wb-feedback-btn" onClick={() => setShowFeedback(true)}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                  </svg>
                  Geef feedback op dit rapport
                </button>
              )
            )}
          </div>
        )}
      </div>
      {showFeedback && (
        <FeedbackModal
          workbook={workbook}
          onClose={() => setShowFeedback(false)}
          onSubmitted={() => { setShowFeedback(false); setFeedbackGiven(true); setFeedbackThanks(true) }}
        />
      )}
      {feedbackThanks && <div className="toast info" role="status">Bedankt voor je feedback!</div>}
      {saveError && (
        <div role="alert" style={{ padding: '8px 24px', color: '#DC2626', fontSize: '.85rem' }}>{saveError}</div>
      )}
      {reportFrame.srcDoc && (
        <ReportFrameFallback probleem={reportFrame.probleem} workbook={workbook} instelling={instelling} save={save} />
      )}
      {/* Focusable so keyboard users can scroll the report (axe: scrollable-region-focusable). */}
      {/* eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex */}
      <div className="wb-viewer-content" style={{ overflowY: 'auto' }} tabIndex={0} role="region" aria-label="Rapportinhoud"
        aria-busy={reportFrame.loading || undefined}>
        {(() => {
          if (BuiltinDash) return <BuiltinDash instelling={instelling} />
          if (spec) return (
            <>
              <GeneratedDashboard
                spec={spec}
                instelling={instelling}
                onRefresh={canRefresh ? handleRefresh : undefined}
                refreshing={refreshing}
              />
              {refreshError && (
                <div role="alert" style={{ padding: '8px 24px', color: '#DC2626', fontSize: '.85rem' }}>{refreshError}</div>
              )}
              {refreshResult && (
                <div role="status" style={{ padding: '8px 24px', fontSize: '.85rem' }}>
                  <div>{refreshResult.melding}</div>
                  {refreshResult.veranderingen.length > 0 && (
                    <ul style={{ margin: '4px 0 0', paddingLeft: 18 }}>
                      {refreshResult.veranderingen.map((v) => <li key={v}>{v}</li>)}
                    </ul>
                  )}
                </div>
              )}
            </>
          )
          if (reportEmpty) return <p className="wb-viewer-empty">Dit rapport heeft geen inhoud.</p>
          return (
            <>
              {reportFrame.loading && (
                <div className="wb-viewer-loading" role="status" aria-busy="true">
                  <span className="spinner" aria-hidden="true" />
                  Rapport wordt geladen…
                </div>
              )}
              {/* allow-popups (escaping the sandbox) lets the source link under each chart open the open-data
                  source in a new tab (#569); without it a click would load that site inside the report frame.
                  The links carry rel="noopener", so the new tab has no way back in. Never allow-same-origin. */}
              <iframe ref={reportFrame.frameRef} className="wb-iframe" srcDoc={reportFrame.srcDoc} title={workbook.title}
                sandbox="allow-scripts allow-popups allow-popups-to-escape-sandbox" onLoad={reportFrame.onLoad} />
            </>
          )
        })()}
      </div>
    </div>
  )
}
