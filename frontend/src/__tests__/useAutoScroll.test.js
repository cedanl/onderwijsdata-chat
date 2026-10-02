// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createElement, useRef, act } from 'react'
import { createRoot } from 'react-dom/client'
import useAutoScroll from '../hooks/useAutoScroll'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

let host
let root
let el
let frames

// jsdom kent geen layout: hoogte en scrollpositie van de berichtenlijst zelf bijhouden.
let scrollTop
let scrollHeight
const CLIENT_HEIGHT = 500

function Chat({ messages }) {
  const ref = useRef(null)
  useAutoScroll(ref, messages)
  return createElement('div', { ref })
}

const render = (messages) => act(async () => { root.render(createElement(Chat, { messages })) })
const flushFrames = () => { const due = frames; frames = []; due.forEach(cb => cb()) }
const userScrollsTo = (top) => { scrollTop = top; el.dispatchEvent(new Event('scroll')) }

const assistant = (content) => ({ id: 'a', role: 'assistant', content })
const user = (id) => ({ id, role: 'user', content: 'vraag' })

beforeEach(async () => {
  frames = []
  vi.stubGlobal('requestAnimationFrame', (cb) => { frames.push(cb); return frames.length })
  vi.stubGlobal('cancelAnimationFrame', () => {})
  scrollTop = 0
  scrollHeight = CLIENT_HEIGHT
  host = document.createElement('div')
  document.body.appendChild(host)
  root = createRoot(host)
  await render([])
  el = host.firstChild
  Object.defineProperties(el, {
    scrollTop: { get: () => scrollTop, set: (v) => { scrollTop = v }, configurable: true },
    scrollHeight: { get: () => scrollHeight, configurable: true },
    clientHeight: { get: () => CLIENT_HEIGHT, configurable: true },
  })
  el.scrollIntoView = vi.fn()
})

afterEach(() => {
  act(() => root.unmount())
  host.remove()
  vi.unstubAllGlobals()
})

describe('useAutoScroll', () => {
  it('volgt een groeiend antwoord direct, zonder smooth-animatie', async () => {
    scrollHeight = 900
    await render([user('u1'), assistant('Het aantal')])
    flushFrames()
    expect(scrollTop).toBe(900)
    expect(el.scrollIntoView).not.toHaveBeenCalled()
  })

  it('scrollt hooguit één keer per frame, hoeveel fragmenten er ook binnenkomen', async () => {
    await render([user('u1'), assistant('Het')])
    await render([user('u1'), assistant('Het aantal')])
    await render([user('u1'), assistant('Het aantal studenten')])
    expect(frames).toHaveLength(1)
  })

  it('laat de positie met rust als de gebruiker omhoog is gescrold', async () => {
    scrollHeight = 2000
    userScrollsTo(300)
    await render([user('u1'), assistant('Het aantal studenten')])
    flushFrames()
    expect(scrollTop).toBe(300)
  })

  it('volgt weer als de gebruiker zelf terug naar onderen scrolt', async () => {
    scrollHeight = 2000
    userScrollsTo(300)
    userScrollsTo(2000 - CLIENT_HEIGHT - 40)
    scrollHeight = 2200
    await render([user('u1'), assistant('Het aantal studenten')])
    flushFrames()
    expect(scrollTop).toBe(2200)
  })

  it('gaat naar onderen na een eigen vraag, ook als de gebruiker omhoog stond', async () => {
    scrollHeight = 2000
    userScrollsTo(300)
    await render([user('u1')])
    flushFrames()
    expect(scrollTop).toBe(2000)
  })
})
