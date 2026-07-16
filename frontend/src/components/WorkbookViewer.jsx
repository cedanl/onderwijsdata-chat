import { useState, useCallback, useRef } from 'react'
import { refreshDashboard as refreshDashboardApi } from '../api'
import { updateWorkbookTitle, updateWorkbookSpec } from '../workbooks'
import { InlineDashboard, InlineDashboardArbeidsmarkt, InlineDashboardRegio, InlineDashboardRegioInstroom, InlineDashboardRegioDiplomering, InlineDashboardRegioArbeidsmarkt } from './InlineDashboards'
import GeneratedDashboard from './GeneratedDashboard'

export default function WorkbookViewer({ workbook, instelling, onBack, onUpdate, backLabel = 'Dashboards' }) {
  const [refreshing, setRefreshing] = useState(false)
  const [refreshError, setRefreshError] = useState(null)
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
      updateWorkbookSpec(workbook.id, freshSpec)
      onUpdate({ ...workbook, dashboardSpec: freshSpec })
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
    updateWorkbookTitle(workbook.id, trimmed)
    onUpdate({ ...workbook, title: trimmed })
    setEditingTitle(false)
  }, [workbook, titleDraft, onUpdate])

  const spec = workbook.dashboardSpec
  const canRefresh = spec && (spec.figure_recipes?.length || spec.recipe?.length)

  return (
    <div className="wb-viewer">
      <div className="wb-viewer-bar">
        <button className="wb-back-btn" onClick={onBack}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="15 18 9 12 15 6" />
          </svg>
          {backLabel}
        </button>
        {editingTitle ? (
          <input
            ref={titleInputRef}
            className="wb-viewer-title"
            value={titleDraft}
            onChange={e => setTitleDraft(e.target.value)}
            onBlur={handleTitleSave}
            onKeyDown={e => { if (e.key === 'Enter') handleTitleSave(); if (e.key === 'Escape') setEditingTitle(false) }}
            style={{ border: 'none', borderBottom: '2px solid var(--primary)', outline: 'none', background: 'transparent', font: 'inherit', padding: 0, width: '100%' }}
          />
        ) : (
          <span
            className="wb-viewer-title"
            onClick={handleTitleEdit}
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
      <div className="wb-viewer-content" style={{ overflowY: 'auto' }}>
        {workbook.id === '__builtin__'
          ? <InlineDashboard instelling={instelling} />
          : workbook.id === '__builtin_arbeidsmarkt__'
          ? <InlineDashboardArbeidsmarkt instelling={instelling} />
          : workbook.id === '__builtin_regio__'
          ? <InlineDashboardRegio instelling={instelling} />
          : workbook.id === '__builtin_regio_instroom__'
          ? <InlineDashboardRegioInstroom instelling={instelling} />
          : workbook.id === '__builtin_regio_diplomering__'
          ? <InlineDashboardRegioDiplomering instelling={instelling} />
          : workbook.id === '__builtin_regio_arbeidsmarkt__'
          ? <InlineDashboardRegioArbeidsmarkt instelling={instelling} />
          : spec
          ? <>
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
          : <iframe className="wb-iframe" srcDoc={workbook.htmlContent} title={workbook.title} sandbox="allow-scripts allow-same-origin" />
        }
      </div>
    </div>
  )
}
