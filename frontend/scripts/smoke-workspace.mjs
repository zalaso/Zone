// Real browser and loopback backend. Only the numerical offline baseline is used.
import assert from 'node:assert/strict'
import { mkdirSync } from 'node:fs'
import { chromium } from 'playwright'

const baseURL = process.env.ZONE_SMOKE_BASE_URL || 'http://127.0.0.1:8767'
if (!/^http:\/\/127\.0\.0\.1:\d+$/.test(baseURL)) throw new Error('Solo anteprima loopback.')
const out = '../benchmark_data/workspace-browser'
mkdirSync(out, { recursive: true })
const browser = await chromium.launch({ ...(process.platform === 'win32' ? { channel: 'msedge' } : {}), headless: true })
let page
try {
  const context = await browser.newContext({ baseURL, viewport: { width: 1440, height: 1000 } })
  page = await context.newPage()
  page.setDefaultTimeout(15_000)
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  await page.goto('/')
  await page.getByLabel('Nome utente').waitFor()
  await page.screenshot({ path: `${out}/access-desktop.png`, fullPage: true })
  const handle = `ws${Date.now().toString(36)}`
  await page.getByLabel('Nome utente').fill(handle)
  await page.getByLabel('Password', { exact: true }).fill('synthetic-browser-password-123')
  await page.getByRole('button', { name: 'Crea account e continua' }).click()
  await page.getByLabel('Codice di recupero').waitFor()
  await page.getByRole('button', { name: 'Ho conservato il codice' }).click()
  await page.getByRole('heading', { name: /Quale universo/ }).waitFor()
  await page.screenshot({ path: `${out}/home-desktop.png`, fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Home senza overflow mobile')
  await page.screenshot({ path: `${out}/home-mobile.png`, fullPage: true })
  await page.getByRole('button', { name: 'Connessioni AI', exact: true }).click()
  await page.getByRole('button', { name: 'ChatGPT', exact: true }).click()
  await page.getByLabel('ID modello').fill('synthetic-not-a-real-model')
  await page.getByRole('button', { name: 'Prepara Sign in with ChatGPT' }).click()
  await page.getByLabel('Chiave del connettore, mostrata una sola volta').waitFor()
  assert(await page.getByLabel('Chiave del connettore, mostrata una sola volta').inputValue())
  await page.getByRole('button', { name: 'Ho conservato la chiave' }).click()
  await page.getByRole('button', { name: 'Usa baseline offline', exact: true }).click()
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Connessioni senza overflow mobile')
  await page.screenshot({ path: `${out}/connections-mobile.png`, fullPage: true })
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.getByRole('button', { name: 'Esplora le modalità', exact: true }).click()
  await page.getByRole('button', { name: /06 Zone Arena/ }).click()
  await page.getByRole('button', { name: 'Registra con il modello selezionato' }).click()
  await page.getByLabel('Agente', { exact: true }).locator('option').nth(1).waitFor({ state: 'attached' })
  await page.getByRole('button', { name: 'Avvia trial personale' }).click()
  await page.getByRole('button', { name: 'Avanza agente · una chiamata' }).waitFor()
  const listing = await (await page.request.get('/v1/my/arena')).json()
  const id = listing.trials.at(-1).session_id
  const expectedExperiments = listing.trials.at(-1).rules.experiment_budget
  let runs = 0
  for (let turn = 0; turn < 20; turn++) {
    const reply = await page.request.get(`/v1/my/arena/trials/${id}`)
    assert(reply.ok(), `Stato Arena HTTP ${reply.status()}: ${await reply.text()}`)
    const state = await reply.json()
    assert.equal(state.executed_experiments, runs, 'Solo il clic Esegui può aumentare i lanci')
    if (state.status === 'scored') break
    const label = {
      discovering: 'Avanza agente · una chiamata', awaiting_submission: 'Avanza agente · una chiamata',
      awaiting_decision: 'Approva richiesta', awaiting_mode: 'Conferma esplorazione Arena',
      ready_to_run: 'Esegui questo esperimento', scoring_pending: 'Completa valutazione',
    }[state.status]
    assert(label, `Stato inatteso ${state.status}`)
    await new Promise(resolve => setTimeout(resolve, 2100)) // respect the account write quota
    await page.getByRole('button', { name: label, exact: true }).click()
    await page.locator('.lab-activity').waitFor({ state: 'hidden' })
    if (state.status === 'ready_to_run') runs++
  }
  const scored = await (await page.request.get(`/v1/my/arena/trials/${id}`)).json()
  assert.equal(scored.status, 'scored')
  assert.equal(scored.executed_experiments, expectedExperiments)
  assert(scored.events.some(event => event.message.type === 'hypothesis'))
  assert(scored.events.some(event => event.message.type === 'conclusion'))
  await page.screenshot({ path: `${out}/arena-desktop.png`, fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Arena senza overflow mobile')
  await page.getByRole('button', { name: 'Le mie sessioni', exact: true }).click()
  await page.getByRole('button', { name: 'Apri indagine', exact: true }).click()
  await page.getByText(`scored · ${expectedExperiments} lanci · ${expectedExperiments} osservazioni`, { exact: true }).waitFor()
  assert.equal(await page.evaluate(() => localStorage.length + sessionStorage.length), 0)
  await page.getByRole('button', { name: 'Esci dall’account', exact: true }).click()
  await page.getByLabel('Nome utente').waitFor()
  assert.deepEqual(errors, [])
  console.log('Workspace browser OK: registrazione, recupero mostrato una volta, connettore senza inferenza, Arena offline con lanci espliciti secondo il budget della challenge, scoring, riapertura, logout; desktop e mobile senza overflow.')
} catch (error) {
  console.error('Messaggi UI:', await page?.getByRole('alert').allTextContents())
  await page?.screenshot({ path: `${out}/failure.png`, fullPage: true })
  throw error
} finally { await browser.close() }
