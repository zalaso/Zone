// Real browser -> Vite -> FastAPI -> SQLite. Only the explicitly labelled offline agent.
import assert from 'node:assert/strict'
import { chromium } from 'playwright'

const token = process.env.ZONE_SMOKE_OPERATOR_TOKEN
assert(token, 'Imposta ZONE_SMOKE_OPERATOR_TOKEN per il backend locale di prova')
const browser = await chromium.launch({ executablePath: process.env.ZONE_BROWSER_EXECUTABLE ?? 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe', headless: true })
const context = await browser.newContext({ baseURL: 'http://127.0.0.1:5173', viewport: { width: 1440, height: 1000 } })
const page = await context.newPage()
page.setDefaultTimeout(60000)
const errors = []
page.on('pageerror', error => errors.push(error.message))
const pause = () => new Promise(resolve => setTimeout(resolve, 2400)) // respect the production write rate limit

async function click(name) {
  await pause()
  console.log(`Azione esplicita: ${name}`)
  const reply = page.waitForResponse(r => r.request().method() === 'POST', { timeout: 60000 })
  await page.getByRole('button', { name, exact: true }).click()
  const response = await reply
  assert(response.ok(), await response.text())
  const data = await response.json()
  await page.locator('.feedback .notice').waitFor()
  return data
}
async function create(mode) {
  const setup = page.locator('.session-setup')
  if (await setup.locator('.setup-toggle').getAttribute('aria-expanded') === 'false') await setup.locator('.setup-toggle').click()
  await page.getByLabel("Mode", { exact: true }).selectOption(mode)
  return click("Create investigation")
}
async function finishAgent(sid) {
  let state = (await (await page.request.get(`/v1/sessions/${sid}`)).json())
  for (let i = 0; i < 50 && state.status !== 'scored'; i++) {
    if (['discovering', 'awaiting_prediction', 'awaiting_submission'].includes(state.status)) state = await click("Ask for next step")
    else if (state.status === 'awaiting_decision') {
      await page.getByLabel("Reason", { exact: true }).fill('Approvazione operativa')
      state = await click("Save decision")
    } else if (state.status === 'awaiting_mode') state = await click("Exploration")
    else if (state.status === 'ready_to_run') state = await click("Run experiment")
    else assert.fail(`Stato inatteso ${state.status}`)
  }
  assert.equal(state.status, 'scored')
  await page.getByRole('heading', { name: "Results", exact: true, level: 2 }).waitFor()
  return state
}
try {
  await page.goto('/')
  await page.getByLabel("Available world").locator('option').first().waitFor({ state: 'attached' })
  await page.getByLabel("Operator token", { exact: true }).fill(token)
  console.log('Pagina fase 6 caricata, avvio Watch an Agent.')
  let created = await create('watch_agent')
  assert.equal(created.agent.real_model, false)
  assert.equal(await page.getByRole('heading', { name: "Propose an experiment" }).count(), 0)
  assert.equal(await page.getByLabel("Agent token", { exact: true }).count(), 0)
  const watched = await finishAgent(created.session_id)
  assert.equal(watched.executed_experiments, 3)
  assert.equal(await page.getByRole('button', { name: "Reveal world", exact: true }).isEnabled(), false)
  console.log(`Watch an Agent offline OK: ${created.session_id}`)

  const match = await create('human_vs_ai')
  assert.equal(await page.getByRole('button', { name: "Agent investigation", exact: true }).isEnabled(), false)
  await page.getByText("Conclude and take the final test", { exact: true }).click()
  await page.getByLabel("Conclusion", { exact: true }).fill('Informazioni insufficienti: non ho effettuato misure.')
  await page.getByLabel("Limits (at least one, one per line)").fill('Zero misure. Questa è solo una prova del flusso.')
  await click("Save conclusion")
  const replay = await (await page.request.get(`/v1/sessions/${match.human_session_id}/events`)).json()
  const probes = replay.events.find(e => e.message.type === 'probe_challenge').message.probes
  for (const [i] of probes.entries()) {
    await page.getByLabel(`ax for state ${i + 1}`, { exact: true }).fill('0')
    await page.getByLabel(`ay for state ${i + 1}`, { exact: true }).fill('0')
  }
  const human = await click("Submit predictions")
  assert.equal(human.status, 'scoring_pending')
  assert.equal(await page.getByRole('heading', { name: "Results", exact: true, level: 2 }).count(), 0)
  await page.getByRole('button', { name: "Agent investigation", exact: true }).click()
  await page.getByRole('heading', { name: "Agent step" }).waitFor()
  await finishAgent(match.agent_session_id)
  const compared = await (await page.request.get(`/v1/matches/${match.match_id}`)).json()
  assert(compared.complete)
  assert(compared.human.scores && compared.agent.scores)
  await page.getByRole('heading', { name: "You", exact: true }).waitFor()
  await page.getByRole('heading', { name: "Agent", exact: true }).waitFor()
  await page.locator('.match-panel').screenshot({ path: '../benchmark_data/web-qa/phase6-match.png' })
  await page.setViewportSize({ width: 390, height: 844 })
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), 'Confronto senza overflow mobile')
  await page.setViewportSize({ width: 1440, height: 1000 })
  console.log(`Human vs AI offline OK: ${match.match_id}`)

  await page.getByLabel("Mode", { exact: true }).selectOption('world_of_day')
  await page.getByText("Today's world is selected.", { exact: true }).waitFor()
  const dayWorld = await page.getByLabel("Available world").inputValue()
  assert.equal(await page.getByLabel("Available world").isEnabled(), false)
  created = await click("Create investigation")
  assert.equal(created.mode, 'world_of_day')
  assert.equal(created.managed_agent, false)
  console.log(`World of the Day locale OK: ${dayWorld}`)

  await page.getByLabel("Mode", { exact: true }).selectOption('build_universe')
  await page.getByLabel("Creation method").selectOption('author')
  const built = await click("Validate and create world")
  assert.equal(await page.getByLabel("Available world").inputValue(), built.world.world_id)
  assert.equal(built.world.builder_version, '1')
  created = await click("Create investigation")
  const publicReplay = await (await page.request.get(`/v1/sessions/${created.session_id}/events`)).json()
  for (const secret of ['"seed"', '"config"', 'secret_grid', 'probe_truth']) assert(!JSON.stringify(publicReplay).includes(secret))
  console.log(`Build a Universe validato OK: ${built.world.world_id}`)
  assert.equal(await page.evaluate(() => localStorage.length + sessionStorage.length), 0)
  await page.screenshot({ path: '../benchmark_data/web-qa/phase6-desktop.png', fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), 'Nessun overflow mobile')
  await page.screenshot({ path: '../benchmark_data/web-qa/phase6-mobile.png', fullPage: true })
  assert.deepEqual(errors, [])
  console.log('Cinque modalità disponibili; percorsi offline reali e viewport mobile OK.')
} catch (error) {
  await page.screenshot({ path: '../benchmark_data/web-qa/phase6-failed.png', fullPage: true }).catch(() => {})
  console.error(await page.locator('.feedback').innerText().catch(() => 'Pagina non disponibile'))
  throw error
} finally { await browser.close() }
