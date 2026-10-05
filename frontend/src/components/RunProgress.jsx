import { useEffect, useState } from 'react'

// Steps the current run has taken: every tool call after the last user message.
export function countRunSteps(messages) {
  const lastUser = messages.findLastIndex(m => m.role === 'user')
  return messages
    .slice(lastUser + 1)
    .reduce((total, m) => total + (m.tools?.length ?? 0), 0)
}

// What the run is doing now: the running step, else the last one taken (UX-10.4).
export function currentRunStep(messages) {
  const lastUser = messages.findLastIndex(m => m.role === 'user')
  const tools = messages.slice(lastUser + 1).flatMap(m => m.tools ?? [])
  const step = tools.findLast(t => !t.done) ?? tools.at(-1)
  return step?.label || null
}

export function formatElapsed(seconds) {
  const m = Math.floor(seconds / 60)
  return `${m}:${String(seconds % 60).padStart(2, '0')}`
}

// A compact total view while a run is going: elapsed time and steps taken (#91).
export default function RunProgress({ busy, steps, stepLabel = null }) {
  const [seconds, setSeconds] = useState(0)

  useEffect(() => {
    if (!busy) return undefined
    const startedAt = Date.now()
    const tick = () => setSeconds(Math.floor((Date.now() - startedAt) / 1000))
    tick()
    const id = setInterval(tick, 1000)
    return () => { clearInterval(id); setSeconds(0) }
  }, [busy])

  if (!busy) return null
  // role=timer: a ticking clock must not be announced by a screen reader.
  return (
    <div className="run-progress" role="timer">
      <span className="run-progress-time">{formatElapsed(seconds)}</span>
      <span aria-hidden="true">·</span>
      <span>{steps} {steps === 1 ? 'stap' : 'stappen'}</span>
      {stepLabel && (
        <>
          <span aria-hidden="true">·</span>
          <span className="run-progress-step">{stepLabel}</span>
        </>
      )}
    </div>
  )
}
