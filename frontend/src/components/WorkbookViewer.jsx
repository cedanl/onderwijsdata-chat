import { useState, useCallback, useRef } from 'react'
import { refreshDashboard as refreshDashboardApi } from '../api'
import { updateWorkbook, BUILTIN_MIJN_INSTELLING, BUILTIN_ARBEIDSMARKT, BUILTIN_NATIONAAL } from '../workbooks'
import { InlineDashboardMijnInstelling, InlineDashboardArbeidsmarkt, InlineDashboardNationaal } from './InlineDashboards'
import GeneratedDashboard from './GeneratedDashboard'

const BUILTIN_COMPONENTS = {
  [BUILTIN_MIJN_INSTELLING.id]: InlineDashboardMijnInstelling,
  [BUILTIN_ARBEIDSMARKT.id]: InlineDashboardArbeidsmarkt,
  [BUILTIN_NATIONAAL.id]: InlineDashboardNationaal,
}

export default function WorkbookViewer({ workbook, instelling, onBack, onUpdate, backLabel = 'Dashboards' }) {
  const [refreshing, setRefreshing] = useState(false)
  const [refreshError, setRefreshError] = useState(null)
  const [saveError, setSaveError] = useState(null)
  const [editingTitle, setEditingTitle] = useState(false)
  const [titleDraft, setTitleDraft] = useState('')
  const titleInputRef = useRef(null)

  const handleRefresh = useCallback(async () => {
    const spec = workbook?.dashboardSpec
    if (refreshing || (!spec?.figure_recipes?.length && !spec?.recipe?.length)) return
    setRefreshing(true)
    setRefreshError(null)
    try {
      const { spec: freshSpec } = await refreshDashboardApi(spec, { instelling })
      onUpdate(await updateWorkbook(workbook, { dashboardSpec: freshSpec }))
    } catch (err) {
      setRefreshError(err.message || 'Verversen mislukt')
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

  return (
    <div className="wb-viewer">
      <div className="wb-viewer-bar">
        <button type="button" className="wb-back-btn" onClick={onBack}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="15 18 9 12 15 6" />
          </svg>
          {backLabel}
        </button>
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
            style={{ cursor: workbook.builtin ? 'default' : 'pointer', display: 'inline-flex', alignItems: 'center', gap: 6 }}
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
        <div />
      </div>
      {saveError && (
        <div role="alert" style={{ padding: '8px 24px', color: '#DC2626', fontSize: '.85rem' }}>{saveError}</div>
      )}
      <div className="wb-viewer-content" style={{ overflowY: 'auto' }}>
        {(() => {
          const BuiltinDash = BUILTIN_COMPONENTS[workbook.id]
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
                <div style={{ padding: '8px 24px', color: '#DC2626', fontSize: '.85rem' }}>{refreshError}</div>
              )}
            </>
          )
          return <iframe className="wb-iframe" srcDoc={workbook.htmlContent} title={workbook.title} sandbox="allow-scripts" />
        })()}
      </div>
    </div>
  )
}
