#!/usr/bin/env node
/**
 * UX-audit voor onderwijsdata-chat (openEDUdata+).
 *
 * Rijdt met Playwright door de hele app — inloggen, onboarding, chat met
 * scopevraag, grafieken, CSV-export, rapport, dashboards, workbooks, feedback,
 * 404, mobiel, a11y — en legt per stap een screenshot, console-fouten,
 * netwerkfouten, WebSocket-frames en timings vast. Elke stap is "zacht": een
 * mislukte stap wordt genoteerd en de audit loopt door.
 *
 * Uitvoer: audit/out/report.json + audit/out/shots/*.png (+ downloads, trace).
 *
 *   AUDIT_BASE_URL  te auditen omgeving (default: test.sdp.surf.nl)
 *   AUDIT_USER      gebruikersnaam
 *   AUDIT_PASS      wachtwoord
 *   AUDIT_OUT       uitvoermap (default: audit/out)
 *   AUDIT_CHAT_TIMEOUT  max. wachttijd per chatantwoord in ms (default: 420000)
 *   AUDIT_SKIP_RATELIMIT=1  sla de login-rate-limit-probe over
 */
import { chromium } from 'playwright'
import fs from 'node:fs'
import path from 'node:path'

const BASE = (process.env.AUDIT_BASE_URL || 'https://onderwijsdata-chat.test.sdp.surf.nl').replace(/\/+$/, '')
const USER = process.env.AUDIT_USER || 'demo'
const PASS = process.env.AUDIT_PASS || ''
const OUT = process.env.AUDIT_OUT || 'audit/out'
const CHAT_TIMEOUT = Number(process.env.AUDIT_CHAT_TIMEOUT || 420_000)
const SKIP_RATELIMIT = process.env.AUDIT_SKIP_RATELIMIT === '1'

const SHOTS = path.join(OUT, 'shots')
const DOWNLOADS = path.join(OUT, 'downloads')
fs.mkdirSync(SHOTS, { recursive: true })
fs.mkdirSync(DOWNLOADS, { recursive: true })

const log = (...a) => console.log(new Date().toISOString().slice(11, 19), ...a)

const report = {
  meta: {
    base: BASE,
    user: USER,
    startedAt: new Date().toISOString(),
    chatTimeoutMs: CHAT_TIMEOUT,
    playwright: (await import('playwright/package.json', { with: { type: 'json' } }).catch(() => ({ default: { version: '?' } }))).default.version,
  },
  endpoints: [],
  steps: [],
  findings: [],
  console: [],
  failedRequests: [],
  wsFrames: [],
  downloads: [],
  metrics: {},
}

function finding(sev, area, title, detail = '', evidence = '') {
  report.findings.push({ sev, area, title, detail, evidence })
  log(`  → [${sev}] ${area}: ${title}`)
}

const save = () => fs.writeFileSync(path.join(OUT, 'report.json'), JSON.stringify(report, null, 2))

// ── browser ──────────────────────────────────────────────────────────────
const browser = await chromium.launch({ headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage'] })
const ctx = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  locale: 'nl-NL',
  timezoneId: 'Europe/Amsterdam',
  acceptDownloads: true,
  permissions: ['clipboard-read', 'clipboard-write'],
  recordHar: { path: path.join(OUT, 'network.har'), content: 'omit' },
})
await ctx.tracing.start({ screenshots: true, snapshots: true })

ctx.on('console', (msg) => {
  const type = msg.type()
  if (type === 'error' || type === 'warning') {
    report.console.push({ type, text: msg.text().slice(0, 400), url: msg.location()?.url?.slice(0, 200) })
  }
})
ctx.on('weberror', (err) => report.console.push({ type: 'pageerror', text: String(err.error()?.message || err).slice(0, 400) }))
ctx.on('requestfailed', (req) =>
  report.failedRequests.push({ url: req.url().slice(0, 220), method: req.method(), failure: req.failure()?.errorText })
)
ctx.on('response', (res) => {
  if (res.status() >= 400) report.failedRequests.push({ url: res.url().slice(0, 220), method: res.request().method(), status: res.status() })
})
ctx.on('download', async (dl) => {
  const file = path.join(DOWNLOADS, dl.suggestedFilename())
  try {
    await dl.saveAs(file)
    const buf = fs.readFileSync(file)
    report.downloads.push({ name: dl.suggestedFilename(), bytes: buf.length, head: buf.toString('utf8').slice(0, 300) })
  } catch (e) {
    report.downloads.push({ name: dl.suggestedFilename(), error: String(e.message) })
  }
  save()
})

const page = await ctx.newPage()

// WebSocket-frames: laat zien wat de server echt stuurt (tool_start, message_cancel, toast, controle …)
page.on('websocket', (ws) => {
  log('  websocket open:', ws.url().slice(0, 90))
  ws.on('framereceived', (ev) => {
    const raw = typeof ev.payload === 'string' ? ev.payload : ''
    let parsed = null
    try { parsed = JSON.parse(raw) } catch { /* niet-JSON */ }
    if (report.wsFrames.length < 1200) {
      report.wsFrames.push({
        t: new Date().toISOString().slice(11, 23),
        type: parsed?.type || 'raw',
        name: parsed?.name,
        label: parsed?.label,
        message: parsed?.message,
        level: parsed?.level,
        controle: parsed?.controle,
        chars: raw.length,
      })
    }
  })
  ws.on('close', () => log('  websocket gesloten'))
})

// ── helpers ──────────────────────────────────────────────────────────────
let stepNo = 0
async function step(name, fn, { shot = true, fullPage = false } = {}) {
  stepNo++
  const rec = { n: stepNo, name, status: 'ok', ms: 0, notes: [], data: {} }
  const t0 = Date.now()
  try {
    const note = await fn(rec)
    if (note) rec.notes.push(note)
  } catch (e) {
    rec.status = 'fout'
    rec.error = String(e?.message || e).split('\n').slice(0, 3).join(' | ')
    finding('middel', name, 'Stap faalde', rec.error)
  }
  rec.ms = Date.now() - t0
  if (shot) {
    const file = `${String(stepNo).padStart(2, '0')}-${name.toLowerCase().replace(/[^a-z0-9]+/g, '-').slice(0, 48)}.png`
    try {
      await page.screenshot({ path: path.join(SHOTS, file), fullPage })
      rec.shot = file
    } catch { /* screenshot is nice-to-have */ }
  }
  report.steps.push(rec)
  save()
  log(`[${rec.status === 'ok' ? ' ok ' : 'FOUT'}] ${String(stepNo).padStart(2, '0')} ${name} (${rec.ms} ms)`)
  return rec
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

/** Wacht tot de send-knop weer "Verstuur bericht" is (= niet meer bezig). */
async function waitForAnswer(timeout = CHAT_TIMEOUT) {
  const t0 = Date.now()
  let ok = true
  await page
    .waitForFunction(() => {
      const btn = document.querySelector('.send-btn')
      return !!btn && btn.getAttribute('aria-label') === 'Verstuur bericht'
    }, { timeout, polling: 500 })
    .catch(() => { ok = false })
  await sleep(600)
  return { ms: Date.now() - t0, ok }
}

const FLUFF = /\b(goede vraag|zeker!|interessant|laten we|geweldige|excellente|ik ga nu)\b/i

/** Lees het laatste assistant-antwoord en beoordeel het op de regels uit prompts/system.md. */
async function analyseAnswer(tag) {
  const info = await page.evaluate(() => {
    const bubbles = [...document.querySelectorAll('.message-bubble-assistant')]
    const last = bubbles.at(-1)
    const steps = [...document.querySelectorAll('.reasoning-step span')].map((n) => n.textContent.trim())
    return {
      text: last?.innerText || '',
      html: last?.innerHTML?.slice(0, 400) || '',
      reasoningSteps: steps,
      snippets: document.querySelectorAll('.reasoning-snippet-block').length,
      figures: document.querySelectorAll('.plotly-figure-wrap').length,
      csvButtons: document.querySelectorAll('.csv-download-btn').length,
      controle: [...document.querySelectorAll('.message-controle')].map((n) => n.innerText),
      stopped: [...document.querySelectorAll('.message-stopped')].map((n) => n.innerText),
      toasts: [...document.querySelectorAll('.toast')].map((n) => n.innerText),
      clarification: [...document.querySelectorAll('.clarification-btn')].map((n) => n.innerText.trim()),
    }
  })
  const text = info.text
  const bigNumbers = [...text.matchAll(/(?<![\w.,])(\d{1,3}(?:[.\u00a0\u202f ]\d{3})+|\d{4,})(?:,\d+)?(?!\w)/g)].map((m) => m[1])
  const checks = {
    hasText: text.trim().length > 0,
    chars: text.length,
    hasBronnen: /\*\*Bronnen\*\*|^Bronnen$/m.test(text),
    hasDefinities: /\*\*Definities\*\*|^Definities$/m.test(text),
    hasMarkdownTable: /\|.*\|[\s\S]*\|[\s-|]+\|/.test(text),
    hasOnderzoeksvraag: /Onderzoeksvraag/i.test(text),
    hasLaatsteUpdate: /(actueel tot|laatste_update|laatst bijgewerkt)/i.test(text),
    mentionsDatasetId: /\b(p\d{2}[a-z0-9]{3,}|\d{5}(?:NED|ENG))\b/.test(text),
    mentionsToolNames: /\b(search_catalog|dataset_details|query_data|compute_kpi|run_analysis|create_plot|get_cbs_data|get_duo_data|get_rio_data|clarify_scope)\b/.test(text),
    fluff: FLUFF.test(text) ? text.match(FLUFF)[0] : null,
    bigNumbers: bigNumbers.length,
    bigNumberSample: bigNumbers.slice(0, 8),
    causalClaim: /\b(dit komt doordat|de reden is|dit betekent dat|veroorzaakt)\b/i.test(text),
  }
  report.metrics[tag] = { ms: info.ms, ...checks, reasoningSteps: info.reasoningSteps.length, snippets: info.snippets, figures: info.figures }
  return { ...info, checks }
}

// ── 1. Server-oppervlak ──────────────────────────────────────────────────
await step('server-endpoints', async (rec) => {
  for (const p of ['/health', '/version', '/info', '/api/config', '/api/auth/status', '/api/catalog/counts']) {
    const t0 = Date.now()
    try {
      const res = await ctx.request.get(BASE + p)
      const body = (await res.text()).slice(0, 500)
      report.endpoints.push({ path: p, status: res.status(), ms: Date.now() - t0, body })
    } catch (e) {
      report.endpoints.push({ path: p, error: String(e.message).slice(0, 160) })
    }
  }
  const root = await ctx.request.get(BASE + '/')
  const h = root.headers()
  rec.data.securityHeaders = {
    'content-security-policy': h['content-security-policy']?.slice(0, 200) || 'ONTBREEKT',
    'x-frame-options': h['x-frame-options'] || 'ONTBREEKT',
    'strict-transport-security': h['strict-transport-security'] || 'ONTBREEKT',
    'x-content-type-options': h['x-content-type-options'] || 'ONTBREEKT',
    'referrer-policy': h['referrer-policy'] || 'ONTBREEKT',
    server: h.server === undefined ? '(leeg/afwezig — goed)' : h.server,
  }
  const missing = Object.entries(rec.data.securityHeaders).filter(([k, v]) => v === 'ONTBREEKT').map(([k]) => k)
  if (missing.length) finding('middel', 'security', 'Ontbrekende security-headers', missing.join(', '))
  rec.notes.push(`${report.endpoints.filter((e) => e.status === 200).length}/${report.endpoints.length} endpoints 200`)
})

// ── 2. Inlogscherm ───────────────────────────────────────────────────────
await step('inlogscherm-laden', async (rec) => {
  await page.goto(BASE + '/', { waitUntil: 'networkidle' })
  rec.data.url = page.url()
  rec.data.title = await page.title()
  rec.data.htmlLang = await page.evaluate(() => document.documentElement.lang || '(leeg)')
  rec.data.metaDescription = await page.evaluate(() => document.querySelector('meta[name=description]')?.content || '(geen)')
  rec.data.favicon = await page.evaluate(() => !!document.querySelector('link[rel*=icon]'))
  if (!rec.data.htmlLang || rec.data.htmlLang === '(leeg)') finding('laag', 'a11y', 'Geen lang-attribuut op <html>', 'Screenreaders kiezen dan de verkeerde taal.')
  if (rec.data.favicon === false) finding('laag', 'ui', 'Geen favicon', '')
  const loginForm = await page.locator('#login-username').count()
  rec.data.loginFormPresent = loginForm > 0
  if (!loginForm) finding('hoog', 'auth', 'Geen inlogformulier gevonden op /', `URL: ${rec.data.url}`)
  rec.data.autocomplete = await page.evaluate(() => ({
    user: document.querySelector('#login-username')?.getAttribute('autocomplete'),
    pass: document.querySelector('#login-password')?.getAttribute('autocomplete'),
  }))
  rec.data.labels = await page.evaluate(() => [...document.querySelectorAll('label')].map((l) => l.textContent.trim()))
  rec.data.sramButton = await page.locator('a[href="/api/auth/oidc/login"]').count()
})

await step('inloggen-verkeerd-wachtwoord', async (rec) => {
  await page.fill('#login-username', USER)
  await page.fill('#login-password', 'verkeerd-wachtwoord-audit')
  const t0 = Date.now()
  await page.click('button[type=submit]')
  await page.waitForSelector('[role=alert]', { timeout: 15_000 }).catch(() => {})
  rec.data.ms = Date.now() - t0
  rec.data.alert = (await page.locator('[role=alert]').first().innerText().catch(() => '')) || '(geen melding)'
  if (rec.data.ms > 3000) finding('laag', 'auth', `Foutief inloggen duurt ${rec.data.ms} ms`, 'Geen feedback tot de server antwoordt.')
  if (!rec.data.alert || rec.data.alert.startsWith('(geen')) finding('hoog', 'auth', 'Geen foutmelding bij verkeerd wachtwoord')
  if (/ongeldig|verkeerd|combinatie/i.test(rec.data.alert) === false) finding('info', 'auth', 'Foutmeldingstekst', rec.data.alert)
})

// ── 3. Inloggen + onboarding ─────────────────────────────────────────────
await step('inloggen', async (rec) => {
  await page.fill('#login-username', USER)
  await page.fill('#login-password', PASS)
  const t0 = Date.now()
  await page.click('button[type=submit]')
  await page.waitForSelector('.navbar', { timeout: 20_000 })
  rec.data.ms = Date.now() - t0
  rec.data.token = await page.evaluate(() => (localStorage.getItem('token') || '').slice(0, 12) + '…')
  report.metrics.loginMs = rec.data.ms
  if (rec.data.ms > 4000) finding('laag', 'auth', `Inloggen duurt ${rec.data.ms} ms`)
})

await step('onboarding-modal', async (rec) => {
  const dlg = page.locator('[role=dialog]')
  rec.data.dialogVisible = await dlg.isVisible().catch(() => false)
  rec.data.ariaLabel = await dlg.getAttribute('aria-label').catch(() => '')
  rec.data.headline = await dlg.locator('h2').innerText().catch(() => '')
  if (!rec.data.dialogVisible) {
    rec.notes.push('Geen onboarding-modal (al eerder onboarded in deze browser-profiel of feature uit)')
  } else {
    // Escape moet sluiten (of expliciet niet bij onboarding) — test en noteer
    await page.keyboard.press('Escape')
    await sleep(500)
    rec.data.closedByEscape = !(await dlg.isVisible().catch(() => false))
    rec.notes.push(`Escape sluit modal: ${rec.data.closedByEscape}`)
  }
})

await step('profiel-instellen', async (rec) => {
  const dlg = page.locator('[role=dialog]')
  if (!(await dlg.isVisible().catch(() => false))) {
    await page.click('button[title="Instellingen"]')
    await page.waitForSelector('[role=dialog]', { timeout: 8000 })
  }
  // Instelling kiezen via de picker
  await page.fill('#settings-instelling', 'Utrecht')
  await sleep(1200)
  const opts = page.locator('#settings-instelling + * li, [role=listbox] [role=option], .instelling-option')
  rec.data.suggestions = (await opts.allInnerTexts().catch(() => [])) || []
  const first = opts.first()
  if (await first.count().catch(() => 0)) await first.click().catch(() => {})
  await page.locator('#settings-instelling').press('Tab')
  // Functie
  await page.getByRole('button', { name: 'Onderzoeker', exact: true }).click().catch(() => {})
  // Thema: donker
  await page.getByRole('button', { name: /Donker/i }).first().click().catch(() => {})
  await page.getByRole('button', { name: /Opslaan|Bewaar|Klaar|Gereed/i }).first().click().catch(async () => {
    await page.keyboard.press('Escape')
  })
  await sleep(800)
  rec.data.darkClass = await page.evaluate(() => document.documentElement.classList.contains('dark'))
  rec.data.savedSettings = await page.evaluate(() => localStorage.getItem('settings'))
  rec.data.instellingInNav = await page.locator('.navbar').innerText().catch(() => '')
})

// ── 4. Startpagina ───────────────────────────────────────────────────────
await step('startpagina', async (rec) => {
  await page.goto(BASE + '/', { waitUntil: 'networkidle' })
  rec.data.h1 = await page.locator('h1').first().innerText().catch(() => '')
  rec.data.stats = await page.evaluate(() =>
    [...document.querySelectorAll('.hero-stat-value')].map((n, i) => `${n.textContent.trim()} ${document.querySelectorAll('.hero-stat-label')[i]?.textContent.trim()}`)
  )
  rec.data.navLabels = await page.evaluate(() => [...document.querySelectorAll('.nav-btn')].map((n) => n.textContent.trim()))
  const counts = report.endpoints.find((e) => e.path === '/api/catalog/counts')?.body
  rec.data.catalogCounts = counts
  rec.notes.push(`Nav: ${rec.data.navLabels.join(', ')}`)
})

// ── 5. Chat: scopevraag ──────────────────────────────────────────────────
await page.goto(BASE + '/chat', { waitUntil: 'networkidle' })

await step('chat-verbinden', async (rec) => {
  await page.waitForSelector('textarea[aria-label="Chatbericht"]', { timeout: 15_000 })
  rec.data.placeholder = await page.getAttribute('textarea[aria-label="Chatbericht"]', 'placeholder')
  rec.data.reconnecting = await page.locator('.ws-reconnecting').count()
  rec.data.modelOptions = await page.evaluate(() => [...document.querySelectorAll('.model-picker option')].map((o) => o.textContent.trim()))
  rec.data.suggestionCategories = await page.locator('.suggested-category-btn').count()
  if (rec.data.reconnecting) finding('middel', 'chat', 'WebSocket niet verbonden bij laden')
})

async function ask(question, tag, { waitClarification = false } = {}) {
  await step(`vraag: ${question.slice(0, 42)}`, async (rec) => {
    await page.fill('textarea[aria-label="Chatbericht"]', question)
    const t0 = Date.now()
    await page.locator('textarea[aria-label="Chatbericht"]').press('Enter')
    const wait = await waitForAnswer()
    rec.data.waitMs = wait.ms
    rec.data.answerArrived = wait.ok
    const a = await analyseAnswer(tag)
    rec.data.answerChars = a.checks.chars
    rec.data.reasoning = a.reasoningSteps
    rec.data.snippets = a.snippets
    rec.data.figures = a.figures
    rec.data.controle = a.controle
    rec.data.stopped = a.stopped
    rec.data.toasts = a.toasts
    rec.data.clarification = a.clarification
    rec.data.checks = a.checks
    rec.data.textPreview = a.text.slice(0, 700)
    if (!wait.ok) finding('hoog', 'chat', `Antwoord niet binnen ${CHAT_TIMEOUT / 1000}s klaar`, question)
    if (a.clarification.length && !waitClarification) rec.notes.push(`Scopevraag met ${a.clarification.length} opties`)
    if (!a.checks.hasText && !a.clarification.length) finding('hoog', 'chat', 'Leeg antwoord', question)
    if (a.checks.fluff) finding('laag', 'toon', 'Verboden opvulwoord in antwoord', a.checks.fluff, a.text.slice(0, 160))
    if (a.checks.mentionsToolNames) finding('middel', 'toon', 'Interne toolnaam lekt in antwoord', '', a.text.match(/\b(search_catalog|query_data|compute_kpi|run_analysis|create_plot|dataset_details|get_\w+_data)\b/)?.[0])
    if (a.checks.hasText && !a.checks.hasBronnen && a.checks.bigNumbers > 0) finding('middel', 'bronvermelding', 'Getallen zonder Bronnen-sectie', `${a.checks.bigNumbers} grote getallen, geen **Bronnen**`)
    if (a.checks.mentionsDatasetId === false && a.checks.bigNumbers > 0) finding('laag', 'bronvermelding', 'Geen dataset-ID genoemd bij getallen')
    if (a.checks.hasLaatsteUpdate === false && a.checks.hasText) rec.notes.push('Geen "actueel tot"-melding (CBS-regel uit de systeemprompt)')
    if (a.controle.length) finding('info', 'controle', 'Servercontrole vond iets', a.controle.join(' | '))
    report.metrics[`${tag}WaitMs`] = wait.ms
  })
  return rec
}

await ask('Hoeveel studenten zijn er?', 'vague', { waitClarification: true })

await step('scopevraag-beantwoorden', async (rec) => {
  const btns = page.locator('.clarification-btn')
  rec.data.options = await btns.allInnerTexts().catch(() => [])
  if (!rec.data.options.length) {
    rec.notes.push('Geen scopekaart — model koos zelf een default (mag volgens de prompt)')
    return
  }
  rec.data.aanbevolen = await page.evaluate(() => [...document.querySelectorAll('.clarification-btn')].map((b) => b.innerText.replace(/\s+/g, ' ')))
  await btns.first().click()
  const wait = await waitForAnswer()
  const a = await analyseAnswer('afterScope')
  rec.data.answerChars = a.checks.chars
  rec.data.checks = a.checks
  rec.data.textPreview = a.text.slice(0, 700)
  rec.data.reasoning = a.reasoningSteps
  if (!wait.ok) finding('hoog', 'chat', 'Geen antwoord na beantwoorden scopevraag')
  // Na een beantwoorde scopevraag mag er géén tweede scopekaart komen (#75)
  const secondClarify = await page.locator('.clarification-btn').count()
  rec.data.secondClarificationCard = secondClarify
  if (secondClarify > rec.data.options.length) finding('middel', 'scope', 'Tweede scopevraag na beantwoorde scopevraag')
})

await ask('Hoeveel studenten waren er in studiejaar 2023/24 ingeschreven in het hbo, uitgesplitst naar opleidingsvorm?', 'specific')

await step('redenering-en-snippet', async (rec) => {
  const toggle = page.locator('.reasoning-toggle').last()
  rec.data.panelPresent = await toggle.count()
  if (!rec.data.panelPresent) {
    finding('middel', 'transparantie', 'Geen redeneerkaart bij een antwoord met toolstappen')
    return
  }
  rec.data.expanded = await toggle.getAttribute('aria-expanded')
  if (rec.data.expanded === 'false') await toggle.click()
  await sleep(500)
  rec.data.steps = await page.locator('.reasoning-step').count()
  rec.data.snippets = await page.locator('.reasoning-snippet-block').count()
  rec.data.snippetPreview = (await page.locator('.reasoning-snippet-block').first().innerText().catch(() => '')).slice(0, 500)
  if (rec.data.snippets === 0) finding('middel', 'reproduceerbaarheid', 'Geen Python-snippets in de redeneerkaart')
})

await step('csv-export-van-grafiek', async (rec) => {
  const btn = page.locator('.csv-download-btn').last()
  rec.data.csvButtons = await page.locator('.csv-download-btn').count()
  if (!rec.data.csvButtons) {
    rec.notes.push('Geen grafiek met CSV-knop in dit gesprek')
    return
  }
  const before = report.downloads.length
  await btn.click()
  await sleep(2500)
  rec.data.downloaded = report.downloads.length - before
  rec.data.file = report.downloads.at(-1)
  if (!rec.data.downloaded) finding('middel', 'export', 'CSV-knop leverde geen download')
})

await step('kopieer-antwoord', async (rec) => {
  const btn = page.locator('.copy-btn-message').last()
  if (!(await btn.count())) {
    rec.notes.push('Geen kopieerknop')
    return
  }
  await btn.click()
  await sleep(700)
  const clip = await page.evaluate(() => navigator.clipboard.readText().catch(() => ''))
  rec.data.clipboardChars = clip.length
  if (!clip.length) finding('laag', 'ui', 'Kopieerknop vulde het klembord niet')
})

// ── 6. Stoppen en busy-gedrag ────────────────────────────────────────────
await step('stoppen-tijdens-genereren', async (rec) => {
  await page.fill('textarea[aria-label="Chatbericht"]', 'Geef een uitgebreide analyse van de instroom in het mbo per provincie over de laatste tien jaar, met grafiek en toelichting.')
  await page.locator('textarea[aria-label="Chatbericht"]').press('Enter')
  await sleep(6000)
  const stopBtn = page.locator('.send-btn[title="Stop genereren"]')
  rec.data.stopVisible = await stopBtn.count()
  if (rec.data.stopVisible) {
    await stopBtn.click()
    await sleep(2500)
    rec.data.stoppedLabel = await page.locator('.message-stopped').last().innerText().catch(() => '(geen label)')
  } else {
    finding('middel', 'chat', 'Geen stopknop zichtbaar tijdens genereren')
  }
  await waitForAnswer(60_000)
})

await step('vraag-tijdens-actief-antwoord', async (rec) => {
  // Servergedrag rechtstreeks via de WebSocket: een tweede vraag tijdens een run moet "busy" geven (#145).
  const token = await page.evaluate(() => localStorage.getItem('token'))
  rec.data.result = await page.evaluate(
    async ({ base, token }) => {
      const wsProto = base.startsWith('https') ? 'wss' : 'ws'
      const ws = new WebSocket(`${base.replace(/^http/, wsProto)}/api/chat?token=${encodeURIComponent(token || '')}`)
      const events = []
      await new Promise((resolve) => {
        const to = setTimeout(resolve, 90_000)
        ws.onmessage = (ev) => {
          let m = {}
          try { m = JSON.parse(ev.data) } catch { /* ignore */ }
          events.push(m.type)
          if (m.type === 'busy' || events.length > 40) { clearTimeout(to); ws.close(); resolve() }
        }
        ws.onopen = async () => {
          ws.send(JSON.stringify({ action: 'message', content: 'Hoeveel mbo-studenten zijn er in Nederland?' }))
          await new Promise((r) => setTimeout(r, 4000))
          ws.send(JSON.stringify({ action: 'message', content: 'En hoeveel in het hbo?' }))
        }
        ws.onerror = () => { clearTimeout(to); resolve() }
      })
      return events
    },
    { base: BASE, token }
  )
  rec.data.busyEvent = rec.data.result.includes('busy')
  if (!rec.data.busyEvent) finding('middel', 'chat', 'Geen busy-event bij tweede vraag tijdens een run', rec.data.result.join(','))
  await page.reload({ waitUntil: 'networkidle' })
  await page.waitForSelector('textarea[aria-label="Chatbericht"]')
  await waitForAnswer(20_000)
})

// ── 7. Zijbalk: suggesties, model, geschiedenis ─────────────────────────
await step('suggestievragen-gepersonaliseerd', async (rec) => {
  const cat = page.locator('.suggested-category-btn').first()
  if (!(await cat.count())) return rec.notes.push('Geen suggestiecategorieën')
  await cat.click()
  await sleep(400)
  rec.data.questions = await page.locator('.suggested-btn').allInnerTexts()
  rec.notes.push(rec.data.questions.slice(0, 3).join(' / '))
  await cat.click()
})

await step('model-picker', async (rec) => {
  const sel = page.locator('.model-picker select')
  rec.data.present = await sel.count()
  if (!rec.data.present) return rec.notes.push('Geen model-picker (AVAILABLE_MODELS niet gezet)')
  rec.data.options = await sel.locator('option').allInnerTexts()
  rec.data.current = await sel.inputValue()
  if (rec.data.options.length > 1) {
    const next = rec.data.options.find((o) => o !== rec.data.current)
    await sel.selectOption({ label: next }).catch(() => {})
    rec.data.afterSwitch = await sel.inputValue()
    rec.data.persisted = await page.evaluate(() => Object.keys(localStorage).filter((k) => /model/i.test(k)).map((k) => `${k}=${localStorage.getItem(k)}`))
    await sel.selectOption({ label: rec.data.current }).catch(() => {})
  }
})

await step('gespreksgeschiedenis-hernoemen', async (rec) => {
  await sleep(1500)
  const items = page.locator('.history-btn')
  rec.data.count = await items.count()
  if (!rec.data.count) return finding('middel', 'persistentie', 'Geen gesprek in de geschiedenis na antwoorden')
  rec.data.titles = await page.locator('.history-btn-title').allInnerTexts()
  const rename = page.locator('.history-action-icon').first()
  await rename.click()
  await page.fill('.title-edit-input', 'Audit-gesprek (hernoemd)')
  await page.keyboard.press('Enter')
  await sleep(1200)
  rec.data.afterRename = await page.locator('.history-btn-title').first().innerText()
  if (!/Audit-gesprek/.test(rec.data.afterRename)) finding('middel', 'persistentie', 'Hernoemen niet zichtbaar', rec.data.afterRename)
})

await step('gesprek-heropenen-na-reload', async (rec) => {
  await page.reload({ waitUntil: 'networkidle' })
  await page.waitForSelector('textarea[aria-label="Chatbericht"]')
  await sleep(1500)
  rec.data.historyAfterReload = await page.locator('.history-btn-title').allInnerTexts()
  rec.data.persisted = rec.data.historyAfterReload.some((t) => /Audit-gesprek/.test(t))
  if (!rec.data.persisted) finding('middel', 'persistentie', 'Hernoemd gesprek niet terug na herladen')
  await page.locator('.history-btn').first().click()
  await sleep(1500)
  rec.data.messagesAfterOpen = await page.locator('.message-bubble-assistant').count()
})

// ── 8. Rapport ───────────────────────────────────────────────────────────
await step('rapport-genereren', async (rec) => {
  await page.goto(BASE + '/chat', { waitUntil: 'networkidle' })
  await page.waitForSelector('textarea[aria-label="Chatbericht"]')
  await sleep(1000)
  await page.fill('textarea[aria-label="Chatbericht"]', 'Hoeveel studenten waren er in studiejaar 2023/24 ingeschreven in het hbo, uitgesplitst naar opleidingsvorm?')
  await page.locator('textarea[aria-label="Chatbericht"]').press('Enter')
  await waitForAnswer()
  const btn = page.locator('.make-rapport-btn')
  rec.data.buttonPresent = await btn.count()
  rec.data.buttonLabel = await btn.innerText().catch(() => '')
  if (!rec.data.buttonPresent) return finding('middel', 'rapport', 'Geen knop "Genereer rapport"')
  const t0 = Date.now()
  await btn.click()
  await page.waitForSelector('.wb-viewer', { timeout: 300_000 }).catch(() => {})
  rec.data.ms = Date.now() - t0
  report.metrics.reportMs = rec.data.ms
  rec.data.url = page.url()
  rec.data.viewer = await page.locator('.wb-viewer').count()
  rec.data.iframe = await page.locator('.wb-iframe').count()
  rec.data.title = await page.locator('.wb-viewer-title').innerText().catch(() => '')
  const html = await page.evaluate(() => document.querySelector('.wb-iframe')?.getAttribute('srcdoc')?.slice(0, 3000) || '')
  rec.data.htmlPreview = html.slice(0, 1200)
  for (const part of ['Onderzoeksvraag', 'Conclusie', 'Definities', 'Bronnen']) {
    if (!html.includes(part)) finding('middel', 'rapport', `Rapport mist "${part}"`)
  }
  if (!rec.data.viewer) finding('hoog', 'rapport', 'Rapport niet geopend binnen 5 minuten')
})

await step('rapport-feedback-geven', async (rec) => {
  const btn = page.locator('.wb-feedback-btn')
  rec.data.buttonPresent = await btn.count()
  if (!rec.data.buttonPresent) return rec.notes.push('Geen feedbackknop (ENABLE_FEEDBACK uit?)')
  await btn.click()
  await page.waitForSelector('.feedback-dialog', { timeout: 10_000 })
  rec.data.questions = await page.locator('.feedback-question').count()
  // Alle vragen beantwoorden: radio's + tekstvelden
  const radios = page.locator('.feedback-dialog input[type=radio]')
  const n = await radios.count()
  for (let i = 0; i < n; i += 1) {
    if (i % 2 === 0) await radios.nth(i).click().catch(() => {})
  }
  const texts = page.locator('.feedback-dialog textarea')
  const tn = await texts.count()
  for (let i = 0; i < tn; i += 1) {
    await texts.nth(i).fill(i === 0 ? 'Audit: mist een duidelijke peildatum per cijfer.' : 'Audit: graag een optie om het rapport als PDF te delen.')
  }
  const submit = page.locator('.feedback-dialog button[type=submit]')
  rec.data.submitDisabledBefore = await submit.isDisabled()
  await submit.click()
  await sleep(2500)
  rec.data.thanks = await page.locator('.wb-feedback-given, .toast').allInnerTexts().catch(() => [])
  if (!rec.data.thanks.length) finding('middel', 'feedback', 'Geen bevestiging na versturen feedback')
})

await step('feedback-dubbel-versturen', async (rec) => {
  const btn = page.locator('.wb-feedback-btn')
  if (!(await btn.count())) return rec.notes.push('Feedbackknop niet meer aanwezig (al gegeven)')
  await btn.click().catch(() => {})
  await page.waitForSelector('.feedback-dialog', { timeout: 6000 }).catch(() => {})
  if (!(await page.locator('.feedback-dialog').count())) return rec.notes.push('Modal opent niet opnieuw')
  await page.locator('.feedback-dialog textarea').first().fill('Audit: tweede inzending om de rate limit te testen.')
  await page.locator('.feedback-dialog button[type=submit]').click().catch(() => {})
  await sleep(2000)
  rec.data.error = await page.locator('.feedback-dialog [role=alert], .feedback-dialog .error, .feedback-dialog').first().innerText().catch(() => '')
  rec.notes.push(rec.data.error.slice(0, 200))
})

await step('rapportenpagina', async (rec) => {
  await page.goto(BASE + '/rapporten', { waitUntil: 'networkidle' })
  await sleep(1200)
  rec.data.cards = await page.locator('.wb-card').count()
  rec.data.titles = await page.locator('.wb-card-title').allInnerTexts().catch(() => [])
  rec.data.empty = await page.locator('text=Nog geen rapporten opgeslagen').count()
})

// ── 9. Dashboards ────────────────────────────────────────────────────────
await step('dashboardpagina', async (rec) => {
  await page.goto(BASE + '/dashboards', { waitUntil: 'networkidle' })
  await sleep(1500)
  rec.data.notFound = await page.locator('.notfound h1').innerText().catch(() => '')
  if (rec.data.notFound) {
    finding('info', 'dashboards', 'Dashboardfunctie staat uit op deze omgeving', rec.data.notFound)
    return
  }
  rec.data.cards = await page.locator('.wb-card').count()
  rec.data.cardTitles = await page.locator('.wb-card-title').allInnerTexts().catch(() => [])
  rec.data.newCard = await page.locator('.wb-new-card').count()
})

await step('vast-dashboard-openen', async (rec) => {
  if (await page.locator('.notfound h1').count()) return rec.notes.push('Dashboards uit')
  const card = page.locator('.wb-card').first()
  if (!(await card.count())) return rec.notes.push('Geen dashboardkaarten')
  rec.data.card = await card.innerText().catch(() => '')
  await card.click()
  await sleep(6000)
  rec.data.figures = await page.locator('.plotly-figure-wrap, .js-plotly-plot').count()
  rec.data.kpis = await page.evaluate(() => [...document.querySelectorAll('[class*=kpi]')].length)
  rec.data.errors = await page.locator('.toast.error, [role=alert]').allInnerTexts().catch(() => [])
  if (!rec.data.figures) finding('middel', 'dashboards', 'Vast dashboard toont geen grafieken', (rec.data.errors || []).join(' | '))
})

await step('dashboard-genereren', async (rec) => {
  if (await page.locator('.notfound h1').count()) return rec.notes.push('Dashboards uit')
  await page.goto(BASE + '/dashboards', { waitUntil: 'networkidle' })
  await sleep(1200)
  const newCard = page.locator('.wb-new-card')
  if (!(await newCard.count())) return rec.notes.push('Geen "Nieuw dashboard"-kaart')
  await newCard.click()
  await page.waitForSelector('.dc-textarea', { timeout: 10_000 })
  rec.data.examples = await page.locator('.dc-example-btn').allInnerTexts().catch(() => [])
  await page.fill('.dc-textarea', 'Toon de instroom in het hbo over de laatste vijf jaar, met een vergelijking tussen voltijd en deeltijd.')
  const t0 = Date.now()
  await page.locator('.dc-textarea').press('Enter')
  // Wacht tot de opslagknop er is of een dashboard verschijnt
  await page.waitForFunction(
    () => document.querySelectorAll('.js-plotly-plot').length > 0 || !!document.querySelector('.dc-save-btn:not([disabled])'),
    { timeout: 420_000, polling: 2000 }
  ).catch(() => {})
  rec.data.ms = Date.now() - t0
  report.metrics.dashboardMs = rec.data.ms
  rec.data.figures = await page.locator('.js-plotly-plot').count()
  rec.data.kpiTexts = await page.evaluate(() => [...document.querySelectorAll('[class*=kpi]')].map((n) => n.innerText.replace(/\n/g, ' ')).slice(0, 8))
  const saveBtn = page.locator('.dc-save-btn')
  rec.data.saveEnabled = await saveBtn.isEnabled().catch(() => false)
  if (rec.data.saveEnabled) {
    await saveBtn.click()
    await sleep(4000)
    rec.data.afterSaveUrl = page.url()
  }
  if (!rec.data.figures) finding('middel', 'dashboards', 'Gegenereerd dashboard zonder grafieken')
})

await step('workbook-verwijderen', async (rec) => {
  await page.goto(BASE + '/dashboards', { waitUntil: 'networkidle' })
  await sleep(1500)
  const del = page.locator('.wb-delete-btn').last()
  if (!(await del.count())) return rec.notes.push('Geen verwijderbaar dashboard')
  await del.click()
  await page.waitForSelector('.confirm-dialog', { timeout: 6000 }).catch(() => {})
  rec.data.confirmText = await page.locator('.confirm-dialog').innerText().catch(() => '')
  const yes = page.locator('.confirm-dialog button').last()
  await yes.click().catch(() => {})
  await sleep(1500)
  rec.data.cardsAfter = await page.locator('.wb-card').count()
})

// ── 10. Databronnen-modal, 404, thema, mobiel, a11y ─────────────────────
await step('databronnen-modal', async (rec) => {
  await page.goto(BASE + '/chat', { waitUntil: 'networkidle' })
  await page.waitForSelector('textarea[aria-label="Chatbericht"]')
  const trigger = page.locator('text=/Databronnen|Bronnen|Data bronnen/i').first()
  rec.data.triggerFound = await trigger.count()
  if (!rec.data.triggerFound) return rec.notes.push('Geen zichtbare trigger voor databronnen in de chat')
  await trigger.click()
  await page.waitForSelector('[aria-label="Databronnen"], .modal-overlay', { timeout: 6000 }).catch(() => {})
  rec.data.modal = await page.locator('[role=dialog]').innerText().catch(() => '')
  rec.notes.push(rec.data.modal.slice(0, 200))
  await page.keyboard.press('Escape')
})

await step('onbekend-pad-404', async (rec) => {
  await page.goto(BASE + '/dit-pad-bestaat-niet', { waitUntil: 'networkidle' })
  rec.data.h1 = await page.locator('.notfound h1').innerText().catch(() => '')
  rec.data.status = await page.evaluate(() => window.__lastStatus || null)
  if (!/bestaat niet/i.test(rec.data.h1 || '')) finding('middel', 'routing', 'Geen 404-pagina op onbekend pad', rec.data.h1)
})

await step('thema-wisselen', async (rec) => {
  await page.click('button[title="Instellingen"]').catch(() => {})
  await page.waitForSelector('[role=dialog]', { timeout: 6000 }).catch(() => {})
  if (!(await page.locator('[role=dialog]').count())) return rec.notes.push('Instellingen niet te openen')
  await page.getByRole('button', { name: /Licht/i }).first().click().catch(() => {})
  await page.getByRole('button', { name: /Opslaan|Bewaar|Klaar|Gereed/i }).first().click().catch(() => {})
  await sleep(900)
  rec.data.darkAfterLight = await page.evaluate(() => document.documentElement.classList.contains('dark'))
  rec.data.settings = await page.evaluate(() => localStorage.getItem('settings'))
})

await step('mobiel-viewport', async (rec) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto(BASE + '/chat', { waitUntil: 'networkidle' })
  await page.waitForSelector('textarea[aria-label="Chatbericht"]')
  await sleep(1200)
  rec.data.overflow = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
  }))
  if (rec.data.overflow.scrollWidth > rec.data.overflow.innerWidth + 2) {
    finding('middel', 'responsive', 'Horizontale overflow op mobiel', JSON.stringify(rec.data.overflow))
  }
  const burger = page.locator('.hamburger-btn')
  rec.data.burger = await burger.count()
  if (rec.data.burger) {
    await burger.click()
    await sleep(600)
    rec.data.sidebarOpen = await page.locator('.chat-sidebar.open').count()
    await burger.click()
  }
  rec.data.mobileTabs = await page.evaluate(() => [...document.querySelectorAll('[class*=mobile] a, [class*=tab] a')].map((n) => n.textContent.trim()).slice(0, 8))
  rec.data.tinyTargets = await page.evaluate(() => {
    const small = []
    for (const el of document.querySelectorAll('button, a')) {
      const r = el.getBoundingClientRect()
      if (r.width > 0 && (r.width < 32 || r.height < 32)) small.push(`${el.getAttribute('aria-label') || el.textContent.trim().slice(0, 20)} (${Math.round(r.width)}×${Math.round(r.height)})`)
    }
    return small.slice(0, 15)
  })
  if (rec.data.tinyTargets.length) finding('laag', 'responsive', 'Kleine tikdoelen op mobiel', rec.data.tinyTargets.join(', '))
  await page.setViewportSize({ width: 1440, height: 900 })
})

await step('toegankelijkheid-sweep', async (rec) => {
  await page.goto(BASE + '/chat', { waitUntil: 'networkidle' })
  await page.waitForSelector('textarea[aria-label="Chatbericht"]')
  rec.data.a11y = await page.evaluate(() => {
    const noName = []
    for (const el of document.querySelectorAll('button, a[href], input, select, textarea')) {
      const name = (el.getAttribute('aria-label') || el.getAttribute('title') || el.textContent || el.getAttribute('placeholder') || '').trim()
      if (!name) noName.push(`${el.tagName}.${el.className}`.slice(0, 60))
    }
    const imgsNoAlt = [...document.querySelectorAll('img')].filter((i) => !i.hasAttribute('alt')).length
    const headings = [...document.querySelectorAll('h1,h2,h3,h4')].map((h) => h.tagName)
    return {
      controlsWithoutName: noName.slice(0, 20),
      controlsWithoutNameCount: noName.length,
      imgsNoAlt,
      headingOrder: headings.join('>'),
      lang: document.documentElement.lang || '(leeg)',
      focusVisible: getComputedStyle(document.querySelector('.send-btn') || document.body).outlineStyle,
    }
  })
  if (rec.data.a11y.controlsWithoutNameCount) finding('laag', 'a11y', `${rec.data.a11y.controlsWithoutNameCount} bedieningselementen zonder toegankelijke naam`, rec.data.a11y.controlsWithoutName.join(', '))
  // Tab-volgorde
  await page.keyboard.press('Tab')
  rec.data.firstTabFocus = await page.evaluate(() => {
    const a = document.activeElement
    return `${a?.tagName}.${a?.className || ''}`.slice(0, 70)
  })
})

await step('uitloggen', async (rec) => {
  const btn = page.locator('button[title="Instellingen"]')
  if (await btn.count()) {
    await btn.click()
    await sleep(500)
  }
  await page.getByRole('button', { name: /Uitloggen/i }).first().click().catch(async () => {
    await page.locator('.navbar-cta').click().catch(() => {})
  })
  await sleep(1500)
  rec.data.backAtLogin = await page.locator('#login-username').count()
  rec.data.tokenCleared = await page.evaluate(() => !localStorage.getItem('token'))
  if (!rec.data.backAtLogin) finding('middel', 'auth', 'Uitloggen brengt niet terug naar het inlogscherm')
})

// ── 11. Rate limit (laatste, want het blokkeert het IP even) ────────────
if (!SKIP_RATELIMIT) {
  await step('login-rate-limit', async (rec) => {
    const statuses = []
    for (let i = 0; i < 7; i += 1) {
      const res = await ctx.request.post(BASE + '/api/auth/login', { data: { username: USER, password: 'fout' } })
      statuses.push(res.status())
      if (i === 6) rec.data.retryAfter = res.headers()['retry-after']
    }
    rec.data.statuses = statuses
    rec.data.limited = statuses.includes(429)
    if (!rec.data.limited) finding('hoog', 'security', 'Login niet rate-limited na 7 pogingen', statuses.join(','))
    await sleep(2000)
    const ui = await page.evaluate(async (base) => {
      const r = await fetch(`${base}/api/auth/login`, {
        method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ username: 'x', password: 'y' }),
      })
      return { status: r.status, body: (await r.text()).slice(0, 200) }
    }, BASE)
    rec.data.uiResponse = ui
  })
}

// ── afronden ─────────────────────────────────────────────────────────────
report.metrics.totalMs = Date.now() - Date.parse(report.meta.startedAt)
report.meta.finishedAt = new Date().toISOString()
report.metrics.stepsOk = report.steps.filter((s) => s.status === 'ok').length
report.metrics.stepsFout = report.steps.filter((s) => s.status === 'fout').length
report.metrics.findings = report.findings.length
report.metrics.consoleErrors = report.console.filter((c) => c.type === 'error' || c.type === 'pageerror').length

save()
await ctx.tracing.stop({ path: path.join(OUT, 'trace.zip') })
await browser.close()

log('── samenvatting ────────────────────────────────────────────')
log(`stappen: ${report.metrics.stepsOk} ok / ${report.metrics.stepsFout} fout · findings: ${report.metrics.findings} · console-errors: ${report.metrics.consoleErrors}`)
for (const f of report.findings) log(`  [${f.sev}] ${f.area} — ${f.title}`)
process.exit(0)
