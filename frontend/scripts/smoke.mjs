// Integration smoke against a running local backend and Vite; no mocked HTTP.
import assert from 'node:assert/strict'
import { chromium } from 'playwright'

const token = process.env.ZONE_SMOKE_OPERATOR_TOKEN
const baseURL = process.env.ZONE_SMOKE_BASE_URL || 'http://127.0.0.1:5173'
if (!/^http:\/\/127\.0\.0\.1:\d+$/.test(baseURL)) throw new Error('Smoke consentito solo su loopback.')
if (!token) throw new Error('Imposta ZONE_SMOKE_OPERATOR_TOKEN per il backend di prova locale.')
const browser = await chromium.launch(process.env.ZONE_BROWSER_EXECUTABLE
  ? { executablePath: process.env.ZONE_BROWSER_EXECUTABLE, headless: true }
  : { channel: 'msedge', headless: true })
try {
  const context = await browser.newContext({ baseURL, viewport: { width: 1280, height: 900 } })
  const page = await context.newPage()
  page.setDefaultTimeout(15_000)
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  await page.goto(`${baseURL}/`)
  await page.getByRole('option').first().waitFor({ state: 'attached' })
  await page.getByLabel("Operator token", { exact: true }).fill(token)
  await page.getByRole('button', { name: "Create investigation", exact: true }).click()
  await page.getByRole('heading', { name: "Propose an experiment" }).waitFor()
  const id = await page.locator('.session-bar').getAttribute('data-session-id')
  console.log('Sessione reale creata.')
  await page.getByLabel("Experiment purpose").fill('Controllare il percorso reale browser–backend.')
  await page.getByRole('button', { name: "Submit proposal", exact: true }).click()
  const decision = page.locator('section').filter({ has: page.getByRole('heading', { name: "Review the proposal" }) })
  await decision.getByLabel("Modify", { exact: true }).check()
  await decision.getByLabel("Duration (s)").fill('0.5')
  await decision.getByLabel("Reason").fill('Tre punti per la verifica locale.')
  await decision.getByRole('button', { name: "Save decision" }).click()
  await page.getByRole('button', { name: "Verification with a prediction" }).click()
  await page.getByLabel("Hypothesis", { exact: true }).fill('Ipotesi provvisoria; dati insufficienti.')
  await page.getByRole('button', { name: "Save hypothesis", exact: true }).click()
  for (const t of ['0', '0.25', '0.5']) {
    await page.getByLabel(`x at ${t} seconds`, { exact: true }).fill('0')
    await page.getByLabel(`y at ${t} seconds`, { exact: true }).fill('0')
  }
  await page.getByRole('button', { name: "Preregister prediction" }).click()
  let state = await (await page.request.get(`/v1/sessions/${id}`)).json()
  assert.equal(state.executed_experiments, 0, 'Nessuna esecuzione implicita')
  await page.getByRole('button', { name: "Run experiment" }).click()
  await page.getByText('3 measurements recorded', { exact: true }).waitFor()
  console.log('Verifica reale eseguita dopo autorizzazione esplicita.')
  await page.getByText("Conclude and take the final test", { exact: true }).click()
  await page.getByLabel("Conclusion", { exact: true }).fill('Percorso verificato; informazioni insufficienti per una legge.')
  await page.getByLabel("Limits (at least one, one per line)").fill('Un solo lancio.')
  await page.getByRole('button', { name: "Save conclusion" }).click()
  await page.getByRole('heading', { name: "Predict new states" }).waitFor()
  const replay = await (await page.request.get(`/v1/sessions/${id}/events`)).json()
  const probes = replay.events.find(event => event.message.type === 'probe_challenge').message.probes
  for (const [i] of probes.entries()) {
    await page.getByLabel(`ax for state ${i + 1}`, { exact: true }).fill('0')
    await page.getByLabel(`ay for state ${i + 1}`, { exact: true }).fill('0')
  }
  await page.getByRole('button', { name: "Submit predictions" }).click()
  await page.getByRole('heading', { name: "Results", exact: true, level: 2 }).waitFor()
  console.log('Submission reale valutata.')
  assert.equal(await page.getByRole('button', { name: "Reveal world", exact: true }).isEnabled(), false)
  state = await (await page.request.get(`/v1/sessions/${id}`)).json()
  assert.equal(state.status, 'scored')
  assert.equal(state.executed_experiments, 1)
  const publicReplay = await (await page.request.get(`/v1/sessions/${id}/events`)).json()
  assert.deepEqual(publicReplay.events.filter(e => ['execution_started', 'observation', 'verification'].includes(e.message.type)).map(e => e.message.type), ['execution_started', 'observation', 'verification'])
  for (const secret of ['"seed"', '"config"', 'secret_grid', 'probe_truth']) assert(!JSON.stringify(publicReplay).includes(secret))
  assert.equal(await page.evaluate(() => localStorage.length + sessionStorage.length), 0)
  await page.screenshot({ path: '../benchmark_data/web-qa/consolidation-desktop.png', fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), 'Nessun overflow mobile')
  await page.getByLabel("I confirm that I want to reveal the private world").check()
  await page.getByRole('button', { name: "Reveal world", exact: true }).click()
  await page.getByRole('heading', { name: "Private record" }).waitFor()
  const clean = await browser.newContext()
  const readOnly = await clean.newPage()
  await readOnly.goto(`${baseURL}/`)
  await readOnly.getByLabel("Investigation identifier", { exact: true }).fill(id)
  await readOnly.getByRole('button', { name: "Open investigation", exact: true }).click()
  await readOnly.getByRole('heading', { name: "Results", exact: true, level: 2 }).waitFor()
  assert.equal(await readOnly.getByRole('heading', { name: "Private record" }).count(), 0)
  assert.equal(await readOnly.getByLabel("Agent token", { exact: true }).inputValue(), '')
  assert.deepEqual(errors, [])
  console.log(`Browser–backend reale OK: sessione ${id}, verifica, submission, replay, reveal esplicito, viewport mobile.`)
} finally { await browser.close() }
