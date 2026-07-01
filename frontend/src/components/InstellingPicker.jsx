import { useState, useEffect, useRef } from 'react'

const NIVEAUS = [
  { id: 'wo',  label: 'WO' },
  { id: 'hbo', label: 'HBO' },
  { id: 'mbo', label: 'MBO' },
]

export function useInstellingen() {
  const [list, setList] = useState([])
  useEffect(() => {
    fetch('/api/instellingen')
      .then(r => r.json())
      .then(setList)
      .catch(() => {})
  }, [])
  return list
}

export default function InstellingPicker({ value, onChange }) {
  const allInstellingen = useInstellingen()
  const [query, setQuery] = useState(value || '')
  const [niveauFilter, setNiveauFilter] = useState(new Set())
  const [open, setOpen] = useState(false)
  const [highlightIdx, setHighlightIdx] = useState(-1)
  const wrapperRef = useRef(null)
  const listRef = useRef(null)

  useEffect(() => { setQuery(value || '') }, [value])

  useEffect(() => {
    const handler = (e) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const filtered = allInstellingen.filter(inst => {
    if (niveauFilter.size > 0 && !niveauFilter.has(inst.type)) return false
    if (!query.trim()) return true
    const q = query.trim().toLowerCase()
    if (inst.naam.toLowerCase().includes(q)) return true
    return inst.aliassen.some(a => a.toLowerCase().includes(q))
  })

  const toggleNiveau = (id) => {
    setNiveauFilter(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
    setOpen(true)
    setHighlightIdx(-1)
  }

  const select = (inst) => {
    setQuery(inst.naam)
    onChange(inst.naam)
    setOpen(false)
    setHighlightIdx(-1)
  }

  const handleKeyDown = (e) => {
    if (!open && (e.key === 'ArrowDown' || e.key === 'Enter')) {
      setOpen(true)
      return
    }
    if (!open) return
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setHighlightIdx(i => Math.min(i + 1, filtered.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setHighlightIdx(i => Math.max(i - 1, 0))
    } else if (e.key === 'Enter' && highlightIdx >= 0 && highlightIdx < filtered.length) {
      e.preventDefault()
      select(filtered[highlightIdx])
    } else if (e.key === 'Escape') {
      setOpen(false)
    }
  }

  useEffect(() => {
    if (highlightIdx >= 0 && listRef.current) {
      const el = listRef.current.children[highlightIdx]
      if (el) el.scrollIntoView({ block: 'nearest' })
    }
  }, [highlightIdx])

  const niveauCounts = {}
  for (const inst of allInstellingen) {
    niveauCounts[inst.type] = (niveauCounts[inst.type] || 0) + 1
  }

  return (
    <div ref={wrapperRef} style={{ position: 'relative' }}>
      <div style={{ display: 'flex', gap: 6, marginBottom: 8 }}>
        {NIVEAUS.map(n => (
          <button
            key={n.id}
            type="button"
            onClick={() => toggleNiveau(n.id)}
            style={{
              padding: '4px 10px', borderRadius: 'var(--radius-sm)', fontSize: '.75rem', fontWeight: 600,
              border: `1.5px solid ${niveauFilter.has(n.id) ? 'var(--blue-500)' : 'var(--gray-200)'}`,
              background: niveauFilter.has(n.id) ? 'var(--blue-50)' : 'var(--white)',
              color: niveauFilter.has(n.id) ? 'var(--blue-700)' : 'var(--gray-500)',
              cursor: 'pointer', transition: 'all .15s',
            }}
          >
            {n.label} {niveauCounts[n.id] ? `(${niveauCounts[n.id]})` : ''}
          </button>
        ))}
      </div>
      <input
        type="text"
        value={query}
        onChange={e => {
          setQuery(e.target.value)
          onChange(e.target.value)
          setOpen(true)
          setHighlightIdx(-1)
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={handleKeyDown}
        placeholder="Zoek op naam of afkorting..."
        autoComplete="off"
        style={{
          width: '100%', padding: '10px 14px',
          border: '1.5px solid var(--gray-200)', borderRadius: 'var(--radius)',
          fontSize: '.9rem', outline: 'none', transition: 'border-color .15s',
          background: 'var(--white)', color: 'var(--gray-900)',
        }}
        onFocusCapture={e => e.target.style.borderColor = 'var(--blue-400)'}
        onBlurCapture={e => e.target.style.borderColor = 'var(--gray-200)'}
      />
      {open && filtered.length > 0 && (
        <div
          ref={listRef}
          style={{
            position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 100,
            marginTop: 4, maxHeight: 220, overflowY: 'auto',
            background: 'var(--white)', border: '1.5px solid var(--gray-200)',
            borderRadius: 'var(--radius)', boxShadow: 'var(--shadow-lg)',
          }}
        >
          {filtered.map((inst, i) => (
            <div
              key={inst.naam}
              onMouseDown={() => select(inst)}
              onMouseEnter={() => setHighlightIdx(i)}
              style={{
                padding: '8px 14px', cursor: 'pointer', fontSize: '.85rem',
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                background: i === highlightIdx ? 'var(--blue-50)' : 'transparent',
              }}
            >
              <span style={{ fontWeight: 500, color: 'var(--gray-900)' }}>{inst.naam}</span>
              <span style={{
                fontSize: '.7rem', fontWeight: 700, textTransform: 'uppercase',
                color: inst.type === 'wo' ? '#7C3AED' : inst.type === 'hbo' ? '#2563EB' : '#0D9488',
                background: inst.type === 'wo' ? '#EDE9FE' : inst.type === 'hbo' ? '#EFF6FF' : '#F0FDFA',
                padding: '2px 6px', borderRadius: 4,
              }}>
                {inst.type}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
