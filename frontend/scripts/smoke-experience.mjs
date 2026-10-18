// Actual loopback app, numerical offline baseline only. No provider login or credentials.
import assert from 'node:assert/strict'
import { mkdirSync } from 'node:fs'
import { chromium } from 'playwright'

const baseURL = process.env.ZONE_SMOKE_BASE_URL || 'http://127.0.0.1:8767'
if (!/^http:\/\/127\.0\.0\.1:\d+$/.test(baseURL)) throw new Error('Solo anteprima loopback.')
const out = '../benchmark_data/experience-browser'
mkdirSync(out, { recursive: true })
const browser = await chromium.launch({ ...(process.platform === 'win32' ? { channel: 'msedge' } : {}), headless: true })
let page
try {
  const context = await browser.newContext({ baseURL, viewport: { width: 1440, height: 1000 } })
  let antivirusInjectionAttempts = 0
  const external = []
  // Isolate this test's network, without changing antivirus or browser settings.
  await context.route('**/*', route => {
    const url = new URL(route.request().url())
    if (url.origin === baseURL) return route.continue()
    if (url.hostname === 'me.kis.v2.scr.kaspersky-labs.com' && url.pathname.endsWith('/main.js')) antivirusInjectionAttempts++
    else external.push(url.origin + url.pathname)
    return route.abort()
  })
  page = await context.newPage(); page.setDefaultTimeout(30_000)
  const errors = [], csp = []
  page.on('pageerror', e => errors.push(e.message))
  page.on('console', msg => { if (/Content Security Policy|violates.*directive/i.test(msg.text())) csp.push(msg.text()) })
  await page.goto('/')
  await page.getByText("Try a demo, no account or AI needed", { exact: true }).click()
  await page.getByRole('button', { name: "Play measurements" }).click()
  await page.waitForFunction(() => Number(document.querySelector('.landing-demo input[type=range]')?.value) > 0)
  await page.screenshot({ path: `${out}/landing.png`, fullPage: true })
  const handle = `ux${Date.now().toString(36)}`
  await page.getByLabel("Username").fill(handle)
  await page.getByLabel('Password', { exact: true }).fill('synthetic-experience-password-123')
  await page.getByRole('button', { name: "Create account and continue" }).click()
  await page.getByLabel("Recovery code").waitFor()
  await page.getByRole('button', { name: "I have saved my code" }).click()
  await page.getByRole('heading', { name: /Which universe/ }).waitFor()
  await page.screenshot({ path: `${out}/home.png`, fullPage: true })
  await page.getByRole('button', { name: "Guide to Zone", exact: true }).click()
  await page.getByLabel("Find a term").fill('prediction')
  assert(await page.locator('.glossary dt').count() > 0)
  await page.getByText("Technical details", { exact: true }).click()
  await page.locator('.technical-notes math').first().waitFor()
  assert(await page.locator('.technical-notes math').first().boundingBox())
  await page.getByRole('button', { name: 'Account', exact: true }).click()
  await page.getByRole('button', { name: "Refresh usage", exact: true }).click()
  await page.getByText(/Usage refreshed at/).waitFor()
  await page.screenshot({ path: `${out}/profile.png`, fullPage: true })
  async function choose(mode) {
    await page.getByRole('button', { name: "Explore modes", exact: true }).click()
    await page.locator('.mode-entry').filter({ hasText: mode }).click()
    const setup = page.locator('.session-setup')
    if (await setup.locator('.setup-toggle').getAttribute('aria-expanded') === 'false') await setup.locator('.setup-toggle').click()
  }
  async function create(mode) {
    await choose(mode)
    const response = page.waitForResponse(r => r.request().method() === 'POST' && /\/(sessions|matches)$/.test(new URL(r.url()).pathname))
    await page.getByRole('button', { name: "Create investigation", exact: true }).click()
    const result = await response; assert(result.ok(), await result.text())
    const data = await result.json()
    await page.locator('.session-bar').waitFor()
    return data
  }
  // Delay only delivery of real local replies, to observe waiting states without fabricating progress.
  async function captureWait(pattern, title, button, file) {
    await page.route(pattern, async route => {
      const response = await route.fetch()
      await new Promise(resolve => setTimeout(resolve, 1200))
      await route.fulfill({ response })
    }, { times: 1 })
    const pending = page.getByRole('button', { name: button, exact: true }).click()
    await page.getByRole('status').filter({ hasText: title }).waitFor()
    if (await page.evaluate(() => matchMedia('(prefers-reduced-motion: reduce)').matches)) assert.equal(await page.locator('.activity-instrument span').first().evaluate(el => getComputedStyle(el).animationName), 'none')
    await page.screenshot({ path: `${out}/${file}.png`, fullPage: true })
    await pending
    await page.getByRole('status').filter({ hasText: title }).waitFor({ state: 'hidden' })
  }
  const day = await create('World of the Day')
  assert.equal(day.mode, 'world_of_day')
  assert.equal(day.managed_agent, false)
  assert.equal(await page.getByLabel("Available world").isEnabled(), false)
  const dayWorld = await page.getByLabel("Available world").inputValue()
  assert(dayWorld, 'Il mondo giornaliero ha un identificativo pubblico')
  await new Promise(resolve => setTimeout(resolve, 2100))
  const sameDay = await create('World of the Day')
  assert.equal(sameDay.mode, 'world_of_day')
  assert.equal(await page.getByLabel("Available world").inputValue(), dayWorld, 'Il mondo giornaliero rimane identico')
  await new Promise(resolve => setTimeout(resolve, 2100))
  await choose('Build a Universe')
  await captureWait('**/v1/worlds/generate', "The laboratory is preparing your world", "Validate and create world", 'world-building')
  await page.getByText(/World accepted/).waitFor()
  await page.getByRole('button', { name: "Create investigation", exact: true }).click()
  await page.getByRole('heading', { name: "Propose an experiment" }).waitFor()
  const id = await page.locator('.session-bar').getAttribute('data-session-id')
  await page.getByLabel("Experiment purpose").fill('Osservare tre campioni, senza suggerire una legge.')
  await page.getByRole('button', { name: "Submit proposal", exact: true }).click()
  const decision = page.locator('.panel').filter({ has: page.getByRole('heading', { name: "Review the proposal", exact: true }) })
  await decision.getByLabel("Modify", { exact: true }).check()
  await decision.getByLabel("Duration (s)").fill('0.5')
  await decision.getByLabel("Reason", { exact: true }).fill('Tre campioni per il test della UI.')
  await decision.getByRole('button', { name: "Save decision" }).click()
  await page.getByRole('button', { name: "Verification with a prediction", exact: true }).click()
  await page.getByLabel("Hypothesis", { exact: true }).fill(String.raw`Ipotesi provvisoria: $a_y=-g$.`)
  await page.locator('.formula-preview math').waitFor()
  await page.getByRole('button', { name: "Save hypothesis", exact: true }).click()
  for (const t of ['0', '0.25', '0.5']) for (const axis of ['x', 'y']) await page.getByLabel(`${axis} at ${t} seconds`, { exact: true }).fill('0')
  await page.getByRole('button', { name: "Preregister prediction", exact: true }).click()
  assert.equal((await (await page.request.get(`/v1/sessions/${id}`)).json()).executed_experiments, 0)
  assert.equal(await page.locator('.public-experiment .observed-path').count(), 0)
  await captureWait('**/v1/sessions/*/run', "Experiment running", "Run experiment", 'experiment-running')
  await page.getByText('3 measurements recorded', { exact: true }).waitFor()
  assert.equal(await page.locator('.public-experiment .sample-point').count(), 3)
  assert.equal(await page.locator('.public-experiment .predicted-path').count(), 1)
  await page.locator('.public-experiment').getByRole('button', { name: "Play measurements" }).click()
  await page.waitForFunction(() => Number(document.querySelector('.public-experiment input[type=range]')?.value) > 0)
  await page.screenshot({ path: `${out}/experiment.png`, fullPage: true })
  await page.getByLabel("History up to this event", { exact: true }).fill('1')
  assert.equal(await page.locator('.public-experiment .sample-point').count(), 0, 'Nessuna misura futura nel replay')
  await page.getByRole('button', { name: "All events", exact: true }).click()
  assert.equal(await page.locator('.public-experiment .sample-point').count(), 3)
  for (const viewport of [{ width: 390, height: 844 }, { width: 768, height: 1024 }]) {
    await page.setViewportSize(viewport)
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Laboratorio senza overflow')
  }
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.screenshot({ path: `${out}/experiment-mobile.png`, fullPage: true })
  await page.setViewportSize({ width: 1440, height: 1000 })
  const watched = await create('Watch an Agent')
  assert.equal(watched.agent.real_model, false)
  await captureWait('**/v1/sessions/*/agent/step', "The agent is preparing a response", "Ask for next step", 'agent-thinking')
  // All pending data still comes from the public history; the next click is explicit.
  await page.getByRole('button', { name: 'Account', exact: true }).click()
  await page.getByRole('button', { name: "Refresh usage", exact: true }).click()
  await page.getByText(/Usage refreshed at/).waitFor()
  await page.setViewportSize({ width: 390, height: 844 })
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Profilo senza overflow')
  await page.screenshot({ path: `${out}/profile-mobile.png`, fullPage: true })
  await choose('World of the Day')
  await page.getByText("Today's world is selected.", { exact: true }).waitFor()
  assert(await page.getByLabel("Available world").isDisabled())
  await choose('Human vs AI')
  assert(await page.getByText(/Investigate first/).isVisible())
  // A fast Chromium runner can finish the preceding scenarios in one IP window.
  // Start the independent full comparison in a fresh window, without weakening quotas.
  await new Promise(resolve => setTimeout(resolve, 60_000))
  const paired = await create('Human vs AI')
  assert.equal(paired.agent.agent.real_model, false)
  await page.getByText("Conclude and take the final test", { exact: true }).click()
  await page.getByLabel("Conclusion", { exact: true }).fill('Informazioni insufficienti: prova del percorso utente.')
  await page.getByLabel("Limits (at least one, one per line)").fill('Nessuna misura; non è una valutazione scientifica.')
  await page.getByRole('button', { name: "Save conclusion", exact: true }).click()
  await page.getByRole('heading', { name: "Predict new states", exact: true }).waitFor()
  const humanEvents = await (await page.request.get(`/v1/sessions/${paired.human_session_id}/events`)).json()
  for (const [i] of humanEvents.events.find(e => e.message.type === 'probe_challenge').message.probes.entries()) for (const axis of ['ax', 'ay']) await page.getByLabel(`${axis} for state ${i + 1}`, { exact: true }).fill('0')
  await page.getByRole('button', { name: "Submit predictions", exact: true }).click()
  await page.getByRole('button', { name: "Agent investigation", exact: true }).click()
  for (let i = 0; i < 35; i++) {
    const stateReply = await page.request.get(`/v1/sessions/${paired.agent_session_id}`)
    assert(stateReply.ok(), `Lettura stato ${stateReply.status()}: ${await stateReply.text()}`)
    const state = await stateReply.json()
    if (state.status === 'scored') break
        await new Promise(resolve => setTimeout(resolve, 2100)) // respect the real write quota
    const labels = { discovering: "Ask for next step", awaiting_submission: "Ask for next step", awaiting_decision: "Save decision", awaiting_mode: "Exploration", ready_to_run: "Run experiment", scoring_pending: "Calculate results" }
    assert(labels[state.status], `Stato inatteso: ${state.status}`)
    if (state.status === 'awaiting_decision') await page.getByLabel("Reason", { exact: true }).fill('Autorizzazione operativa.')
    const reply = page.waitForResponse(r => r.request().method() === 'POST' && r.url().includes(`/v1/sessions/${paired.agent_session_id}/`))
    await page.getByRole('button', { name: labels[state.status], exact: true }).click()
    const response = await reply; assert(response.ok(), await response.text())
    await page.locator('.lab-activity').waitFor({ state: 'hidden' })
  }
  const match = await (await page.request.get(`/v1/matches/${paired.match_id}`)).json()
  assert(match.complete, 'Confronto completato da entrambi')
  await page.screenshot({ path: `${out}/human-vs-ai-mobile.png`, fullPage: true })
  assert.deepEqual(errors, [])
  assert.deepEqual(csp, [], 'Nessuna violazione CSP, comprese le formule')
  assert.deepEqual(external, [], 'Nessuna richiesta esterna del prodotto, font remoti o provider')
  assert.equal(await page.evaluate(() => localStorage.length + sessionStorage.length), 0)
  console.log(`Esperienza browser OK: esempio, guida, profilo, Forge reale, attese, modifica, previsione LaTeX/MathML, lancio esplicito, replay senza futuro, confronto Human vs AI completo, mobile/tablet e movimento ridotto; zero richieste esterne del prodotto o violazioni CSP. Tentativi di iniezione script dell’antivirus bloccati soltanto nel test: ${antivirusInjectionAttempts}.`)
} catch (error) {
  console.error(error.stack)
  console.error('Messaggi UI:', await page?.getByRole('alert').allTextContents())
  await page?.screenshot({ path: `${out}/failure.png`, fullPage: true })
  throw error
} finally { await browser.close() }
