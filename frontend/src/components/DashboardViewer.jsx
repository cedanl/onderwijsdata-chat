import { useState, useCallback, useRef } from 'react'
import { refreshDashboard as refreshDashboardApi } from '../api'
import { updateWorkbookTitle } from '../workbooks'
import { InlineDashboard, InlineDashboardArbeidsmarkt } from './InlineDashboards'
import GeneratedDashboard from './GeneratedDashboard'

export default function DashboardViewer({ workbook, instelling, onBack, onUpdate }) {
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
          Dashboards
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
            style={{ cursor: workbook.builtin ? 'default' : 'pointer' }}
            title={workbook.builtin ? undefined : 'Klik om titel te bewerken'}
          >
            {workbook.title}
          </span>
        )}
        <div />
      </div>
      <div className="wb-viewer-content" style={{ overflowY: 'auto' }}>
        {workbook.id === '__builtin__'
          ? <InlineDashboard instelling={instelling} />
          : workbook.id === '__builtin_arbeidsmarkt__'
          ? <InlineDashboardArbeidsmarkt instelling={instelling} />
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
          : <iframe className="wb-iframe" srcDoc={workbook.htmlContent} title={workbook.title} sandbox="allow-scripts" />
        }
      </div>
    </div>
  )
}
