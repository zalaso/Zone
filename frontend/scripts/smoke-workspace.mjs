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
  await page.getByLabel("Username").waitFor()
  await page.screenshot({ path: `${out}/access-desktop.png`, fullPage: true })
  const handle = `ws${Date.now().toString(36)}`
  await page.getByLabel("Username").fill(handle)
  await page.getByLabel('Password', { exact: true }).fill('synthetic-browser-password-123')
  await page.getByRole('button', { name: "Create account and continue" }).click()
  await page.getByLabel("Recovery code").waitFor()
  await page.getByRole('button', { name: "I have saved my code" }).click()
  await page.getByRole('heading', { name: /Which universe/ }).waitFor()
  await page.screenshot({ path: `${out}/home-desktop.png`, fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Home senza overflow mobile')
  await page.screenshot({ path: `${out}/home-mobile.png`, fullPage: true })
  await page.getByRole('button', { name: "AI connections", exact: true }).click()
  await page.getByRole('button', { name: 'ChatGPT', exact: true }).click()
  await page.getByLabel("Model ID").fill('synthetic-not-a-real-model')
  await page.getByRole('button', { name: "Set up Sign in with ChatGPT" }).click()
  await page.getByLabel("Connector key, shown only once").waitFor()
  assert(await page.getByLabel("Connector key, shown only once").inputValue())
  await page.getByRole('button', { name: "I have saved the key" }).click()
  await page.getByRole('button', { name: "Use offline baseline", exact: true }).click()
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Connessioni senza overflow mobile')
  await page.screenshot({ path: `${out}/connections-mobile.png`, fullPage: true })
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.getByRole('button', { name: "Explore modes", exact: true }).click()
  await page.getByRole('button', { name: /Zone Arena/ }).click()
  await page.getByRole('button', { name: "Register with the selected model" }).click()
  await page.getByLabel("Agent", { exact: true }).locator('option').nth(1).waitFor({ state: 'attached' })
  await page.getByRole('button', { name: "Start your trial" }).click()
  await page.getByRole('button', { name: "Ask for next step · one call" }).waitFor()
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
      discovering: "Ask for next step · one call", awaiting_submission: "Ask for next step · one call",
      awaiting_decision: "Approve proposal", awaiting_mode: "Confirm Arena exploration",
      ready_to_run: "Run this experiment", scoring_pending: "Complete evaluation",
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
  await page.getByRole('button', { name: "My investigations", exact: true }).click()
  await page.getByRole('button', { name: "Open investigation", exact: true }).click()
  await page.getByText(`Results available · ${expectedExperiments} experiments · ${expectedExperiments} observations`, { exact: true }).waitFor()
  assert.equal(await page.evaluate(() => localStorage.length + sessionStorage.length), 0)
  await page.getByRole('button', { name: "Sign out", exact: true }).click()
  await page.getByLabel("Username").waitFor()
  assert.deepEqual(errors, [])
  console.log('Workspace browser OK: registrazione, recupero mostrato una volta, connettore senza inferenza, Arena offline con lanci espliciti secondo il budget della challenge, scoring, riapertura, logout; desktop e mobile senza overflow.')
} catch (error) {
  console.error('Messaggi UI:', await page?.getByRole('alert').allTextContents())
  await page?.screenshot({ path: `${out}/failure.png`, fullPage: true })
  throw error
} finally { await browser.close() }
