import { useEffect, useState } from 'react'

// Tools that take minutes rather than seconds (#547): a run that starts one says so.
export const HEAVY_TOOLS = new Set(['get_uwv_vacatures', 'get_roa_benchmark'])

// The tool calls of the current run: every one after the last user message.
function runTools(messages) {
  const lastUser = messages.findLastIndex(m => m.role === 'user')
  return messages.slice(lastUser + 1).flatMap(m => m.tools ?? [])
}

// Steps the current run has taken.
export function countRunSteps(messages) {
  return runTools(messages).length
}

// What the run is doing now: the running step, else the last one taken (UX-10.4).
export function currentRunStep(messages) {
  const tools = runTools(messages)
  const step = tools.findLast(t => !t.done) ?? tools.at(-1)
  return step?.label || null
}

// Whether the current run has started a heavy tool, running or done.
export function heavyRun(messages) {
  return runTools(messages).some(t => HEAVY_TOOLS.has(t.name))
}

// What to expect, as a fixed line under the timer. A heavy tool says minutes at once (#547); any other run
// says it once the server calls it slow (run_slow after RUN_SLOW_S, #599). The heavy line is the more precise one.
export function waitNote({ heavy = false, slow = false }) {
  if (heavy) return 'Dit kan 2–3 minuten duren.'
  if (slow) return 'Dit kan even duren, soms een paar minuten.'
  return null
}

export function formatElapsed(seconds) {
  const m = Math.floor(seconds / 60)
  return `${m}:${String(seconds % 60).padStart(2, '0')}`
}

// A compact total view while a run is going: elapsed time and steps taken (#91).
// heavy, slow: a fixed line on what to expect, outside the timer element (#547, #599).
export default function RunProgress({ busy, steps, stepLabel = null, heavy = false, slow = false }) {
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
  // The group keeps the note next to the timer in the flex column of messages.
  return (
    <div className="run-progress-group">
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
      {/* A polite status region, mounted empty with the timer: the slow line replaces a toast that was read
          out, and a region that mounts together with its text is often not announced (#532). */}
      <p className="run-progress-note" role="status">{waitNote({ heavy, slow })}</p>
    </div>
  )
}
