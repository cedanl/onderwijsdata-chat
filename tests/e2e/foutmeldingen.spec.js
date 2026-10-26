// #703: elke foutmelding biedt een vervolgstap, lekt geen technische details en blijft na herstel niet hangen.
//
// De teksten komen uit fixtures/foutmeldingen.json; tests/test_foutmeldingen_vervolgstap.py (pytest, wel in CI) houdt dat
// bestand gelijk aan wat core/errors.py maakt en toetst daar de vervolgstap en het ontbreken van lekken op de bron.
// Hier gaat het om wat de gebruiker in de pagina ziet: de melding, de knoppen eronder en wat er na een geslaagde
// herhaling van overblijft.
//
// Draait zonder LLM: de chat-socket is nagebootst (routeWebSocket) en antwoordt per vraag met een fout of met een
// geslaagde beurt. Niet in CI. Draaien: `npx playwright test foutmeldingen` (playwright.config.js).
import { test, expect } from 'playwright/test'
import { readFileSync } from 'node:fs'
import { handleLoginIfNeeded } from './helpers.js'

const MELDINGEN = JSON.parse(readFileSync(new URL('./fixtures/foutmeldingen.json', import.meta.url), 'utf8'))

const VRAAG = 'Hoeveel studenten volgen een hbo-opleiding?'
const ANTWOORD = 'Dat zijn er ruim 470.000, volgens de DUO-inschrijvingen.'

// Wat een gebruiker nooit in een foutmelding hoort te zien.
const TECHNISCH = /Traceback|\.py\b|\.parquet|\/app\/|\/home\/|File "|[{}]|Exception|Error:/i
// Een werkwoord in gebiedende wijs dat de gebruiker iets te doen geeft, of een knop in de pagina.
const VERVOLGSTAP = /\b(probeer|wacht|controleer|kies|stel|geef)\b/i

// De socket: elke vraag krijgt het volgende antwoord uit `beurten`; een fout is het event uit de fixture.
function nabootsSocket(page, beurten) {
  return page.routeWebSocket(/\/api\/chat/, ws => {
    ws.onMessage(tekst => {
      const bericht = JSON.parse(tekst)
      if (bericht.action === 'ping') ws.send(JSON.stringify({ type: 'pong' }))
      if (bericht.action !== 'message') return
      const beurt = beurten.shift()
      if (!beurt) throw new Error(`geen beurt meer klaar voor "${bericht.content}"`)
      for (const ev of beurt) ws.send(JSON.stringify(ev))
    })
  })
}

const geslaagd = [
  { type: 'message_start' },
  { type: 'text_delta', content: ANTWOORD },
  { type: 'message_end', content: ANTWOORD, citaties: [] },
]
const fout = naam => [{ type: 'message_start' }, MELDINGEN[naam]]

async function open(page, beurten) {
  await nabootsSocket(page, beurten)
  await page.goto('/chat')
  await handleLoginIfNeeded(page)
  await expect(page.locator('.chat-welcome')).toBeVisible()
  await expect(page.locator('.ws-reconnecting')).toHaveText('')
}

async function stel(page, vraag) {
  await page.locator('textarea.chat-input').fill(vraag)
  await page.getByRole('button', { name: 'Verstuur bericht' }).click()
}

// De gebruiker moet de fout kunnen oplossen met wat de pagina biedt: een knop, of een zin die zegt wat te doen.
const hulp = bubbel => bubbel.locator('.message-retry button')

for (const naam of Object.keys(MELDINGEN)) {
  test(`${naam}: de melding biedt een vervolgstap en lekt niets technisch`, async ({ page }) => {
    await open(page, [fout(naam)])
    await stel(page, VRAAG)

    const bubbel = page.locator('.message-bubble-error')
    await expect(bubbel).toHaveCount(1)
    const tekst = (await bubbel.innerText()).trim()
    expect(tekst, 'de bubbel toont de servermelding').toContain(MELDINGEN[naam].message.replace('❌ ', '').slice(0, 30))
    expect(tekst).not.toMatch(TECHNISCH)

    const knoppen = await hulp(bubbel).allInnerTexts()
    expect(knoppen.length > 0 || VERVOLGSTAP.test(tekst), 'knop of zin met een vervolgstap').toBe(true)
  })
}

test('een modelfout biedt "Opnieuw", en een ander model als dat er is', async ({ page }) => {
  await open(page, [fout('limiet')])
  await stel(page, VRAAG)
  const bubbel = page.locator('.message-bubble-error')
  await expect(bubbel).toHaveCount(1)

  const knoppen = await hulp(bubbel).allInnerTexts()

  expect(knoppen[0]).toBe('Opnieuw')
  expect(knoppen.slice(1).every(t => t.startsWith('Opnieuw met '))).toBe(true)
})

test('een interne fout biedt alleen "Opnieuw": een ander model lost een fout in de code niet op', async ({ page }) => {
  await open(page, [fout('intern')])
  await stel(page, VRAAG)
  const bubbel = page.locator('.message-bubble-error')
  await expect(bubbel).toHaveCount(1)

  expect(await hulp(bubbel).allInnerTexts()).toEqual(['Opnieuw'])
})

test('na een geslaagde herhaling blijft de fout niet als waarschuwing staan', async ({ page }) => {
  await open(page, [fout('limiet'), geslaagd])
  await stel(page, VRAAG)
  const bubbel = page.locator('.message-bubble-error')
  await expect(bubbel).toHaveCount(1)

  await hulp(bubbel).first().click()

  await expect(page.locator('.message-bubble-assistant', { hasText: ANTWOORD })).toBeVisible()
  // De oude melding mag in het gesprek blijven staan als geschiedenis, maar biedt geen herhaling meer aan en geeft
  // geen toast of verbindingswaarschuwing meer.
  await expect(page.locator('.message-bubble-error .message-retry button')).toHaveCount(0)
  await expect(page.locator('.toast, .ws-reconnecting').filter({ hasText: /\S/ })).toHaveCount(0)
})

test('een verbinding die wegvalt tijdens de beurt zegt wat de gebruiker nu doet', async ({ page }) => {
  await page.routeWebSocket(/\/api\/chat/, ws => {
    ws.onMessage(tekst => {
      const bericht = JSON.parse(tekst)
      if (bericht.action === 'ping') ws.send(JSON.stringify({ type: 'pong' }))
      if (bericht.action === 'message') {
        ws.send(JSON.stringify({ type: 'message_start' }))
        ws.close()
      }
    })
  })
  await page.goto('/chat')
  await handleLoginIfNeeded(page)
  await expect(page.locator('.chat-welcome')).toBeVisible()

  await stel(page, VRAAG)

  const tekst = await page.locator('.message-bubble-assistant').last().innerText()
  expect(tekst).not.toMatch(TECHNISCH)
  expect(tekst).toMatch(VERVOLGSTAP)
})
