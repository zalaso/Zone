// Real Edge -> Vite -> FastAPI -> SQLite. Synthetic BYOA messages, no LLM calls.
import assert from 'node:assert/strict'
import { chromium } from 'playwright'

const operator = process.env.ZONE_SMOKE_OPERATOR_TOKEN
if (!operator) throw new Error('Imposta il token del backend locale di prova.')
const browser = await chromium.launch(process.env.ZONE_BROWSER_EXECUTABLE
  ? { executablePath: process.env.ZONE_BROWSER_EXECUTABLE, headless: true }
  : { channel: 'msedge', headless: true })
const stamp = Date.now().toString()
try {
  const context = await browser.newContext({ baseURL: 'http://127.0.0.1:5173', viewport: { width: 1280, height: 900 } })
  const page = await context.newPage()
  page.setDefaultTimeout(60_000)
  const errors = []
  page.on('pageerror', e => errors.push(e.message))
  await page.goto('/')
  await page.getByRole('option').first().waitFor({ state: 'attached' })
  await page.getByRole('button', { name: 'Zone Arena', exact: true }).click()
  await page.getByLabel('Token operatore Arena').fill(operator)
  await page.getByRole('button', { name: 'Connetti Arena', exact: true }).click()
  await page.getByLabel('Nome challenge').fill(`Smoke Arena ${stamp}`)
  await page.getByRole('button', { name: 'Crea challenge', exact: true }).click()
  await page.getByLabel('Challenge selezionata').locator('option').filter({ hasText: `Smoke Arena ${stamp}` }).waitFor({ state: 'attached' })
  const cid = await page.getByLabel('Challenge selezionata').inputValue()
  const agentName = `BYOA simulato ${stamp}`
  await page.getByLabel('Nome agente').fill(agentName)
  await page.getByLabel('Modello dichiarato').fill('simulated-browser-v1')
  await page.getByRole('button', { name: 'Registra agente', exact: true }).click()
  const token = await page.getByLabel('Token agente Arena').inputValue()
  assert.ok(token.startsWith('za_'))
  const headers = credential => ({ 'X-Zone-Arena-Version': '1', 'X-Zone-Token': credential })
  let key = 0
  async function write(path, body, credential = token) {
    const response = await page.request.post(`/v1/arena/${path}`, { data: body,
      headers: { ...headers(credential), 'Idempotency-Key': `browser-${stamp}-${++key}` } })
    assert.ok(response.ok(), `HTTP ${response.status()}: ${await response.text()}`)
    return response.json()
  }
  async function read(sid) { return (await page.request.get(`/v1/arena/sessions/${sid}`, { headers: headers(token) })).json() }
  const created = await write('sessions', { challenge_id: cid })
  const sid = created.session_id
  await write(`sessions/${sid}/messages`, { expected_version: created.version, message: {
    type: 'experiment_request', request_id: 'browser_e1', purpose: 'Verificare il ciclo reale BYOA, senza modello.',
    experiment: { initial_position: { x: 0, y: 0 }, initial_velocity: { x: 1, y: 2 }, duration: .5, observation_interval: .25 },
  } })
  await page.getByRole('button', { name: 'Aggiorna Arena', exact: true }).click()
  await page.getByRole('button', { name: `${agentName} · awaiting_decision`, exact: true }).click()
  await page.getByRole('button', { name: 'Approva richiesta Arena', exact: true }).click()
  await page.getByRole('button', { name: 'Conferma esplorazione Arena', exact: true }).click()
  await page.getByRole('button', { name: 'Esegui esperimento Arena', exact: true }).waitFor()
  assert.equal((await read(sid)).executed_experiments, 0)
  await page.getByRole('button', { name: 'Esegui esperimento Arena', exact: true }).click()
  await page.getByRole('heading', { name: `${agentName} · discovering`, exact: true }).waitFor()
  let snapshot = await read(sid)
  assert.equal(snapshot.executed_experiments, 1)
  assert.equal(snapshot.events.filter(e => e.message.type === 'observation')[0].message.points.length, 3)
  assert.equal((await page.request.get(`/v1/sessions/${sid}/events`)).status(), 404)
  await write(`sessions/${sid}/messages`, { expected_version: snapshot.version, message: {
    type: 'hypothesis', hypothesis_id: 'browser_h1', statement: 'Ipotesi provvisoria della prova software.',
    uncertainties: ['Una sola misura'], evidence: ['browser_e1'],
  } })
  snapshot = await read(sid)
  await write(`sessions/${sid}/messages`, { expected_version: snapshot.version, message: {
    type: 'conclusion', final_hypothesis_id: 'browser_h1', summary: 'Dati insufficienti per una legge.',
    evidence: ['browser_e1'], limits: ['Prova software, non risultato scientifico'], alternatives: ['Molte leggi'],
  } })
  snapshot = await read(sid)
  const submission = { predictions: snapshot.events.find(e => e.message.type === 'probe_challenge').message.probes.map(p => ({ probe_id: p.probe_id, ax: 0, ay: 0 })) }
  await write(`sessions/${sid}/submission`, { expected_version: snapshot.version, submission })
  await page.getByRole('button', { name: 'Aggiorna Arena', exact: true }).click()
  await page.getByText('RMSE interpolation · valori minori prima', { exact: true }).waitFor()
  await page.getByRole('heading', { name: `${agentName} · scored`, exact: true }).waitFor()
  await page.getByRole('button', { name: 'Chiudi challenge', exact: true }).click()
  await page.getByLabel('Challenge selezionata').locator('option').filter({ hasText: `Smoke Arena ${stamp} · chiusa` }).waitFor({ state: 'attached' })
  const agents = await (await page.request.get('/v1/arena/agents', { headers: headers(operator) })).json()
  const registered = agents.agents.find(a => a.name === agentName)
  await page.getByRole('button', { name: `Revoca token ${registered.tokens[0].token_id.slice(0, 12)}`, exact: true }).click()
  await page.getByText('revocato', { exact: false }).first().waitFor()
  assert.equal((await page.request.get(`/v1/arena/sessions/${sid}`, { headers: headers(token) })).status(), 401)
  assert.deepEqual(await page.evaluate(() => ({ local: localStorage.length, session: sessionStorage.length })), { local: 0, session: 0 })
  const markup = await page.content()
  for (const forbidden of ['probe_truth', 'secret_grid', 'generator_seed']) assert.ok(!markup.includes(forbidden))
  await page.screenshot({ path: '../benchmark_data/web-qa/arena-desktop.png', fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  const width = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, view: innerWidth }))
  assert.ok(width.scroll <= width.view, `Overflow mobile: ${JSON.stringify(width)}`)
  await page.screenshot({ path: '../benchmark_data/web-qa/arena-mobile.png', fullPage: true })
  assert.deepEqual(errors, [])
  console.log(JSON.stringify({ verified: 'Arena reale browser/backend, BYOA simulato, nessun LLM', challenge_id: cid, session_id: sid, experiments: 1, observations: 1, token_revoked: true, mobile_overflow: false }))
} finally { await browser.close() }
