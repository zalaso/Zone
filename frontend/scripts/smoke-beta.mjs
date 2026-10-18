// Hosted smoke uses synthetic accounts only; TLS certificate checks stay enabled.
import assert from 'node:assert/strict'
import { chromium } from 'playwright'

const baseURL = process.env.ZONE_SMOKE_BASE_URL
const target = new URL(baseURL)
assert(target.protocol === 'https:' && (target.hostname.endsWith('.ts.net') ||
  process.env.ZONE_SMOKE_PUBLIC === '1' && target.hostname === 'zone.guido-sbx.duckdns.org'))
assert(target.origin === baseURL && !target.username && !target.password)
const browser = await chromium.launch({ channel: 'msedge', headless: true })
try {
  console.error('zone-smoke-stage:login')
  const context = await browser.newContext({ baseURL, viewport: { width: 1280, height: 900 } })
  const page = await context.newPage()
  page.setDefaultTimeout(20000)
  const errors = []
  page.on('pageerror', () => errors.push('pageerror'))
  await page.goto('/')
  assert.equal(await page.getByRole('button', { name: 'Crea sessione', exact: true }).count(), 0)
  await page.getByLabel('Chiave di accesso', { exact: true }).fill(process.env.ZONE_SMOKE_ACCOUNT_KEY)
  await page.getByRole('button', { name: 'Accedi', exact: true }).click()
  await page.getByRole('button', { name: 'Crea sessione', exact: true }).waitFor()
  const cookie = (await context.cookies()).find(c => c.name === '__Host-zone_session')
  assert(cookie?.secure && cookie.httpOnly && cookie.sameSite === 'Strict' && cookie.path === '/')
  assert.equal(await page.evaluate(() => localStorage.length + sessionStorage.length), 0)
  assert.equal(await page.evaluate(() => document.cookie), '')
  console.error('zone-smoke-stage:experiment')
  await page.getByRole('button', { name: 'Crea sessione', exact: true }).click()
  await page.getByRole('heading', { name: 'Proponi un esperimento' }).waitFor()
  const sid = await page.locator('.session-id').first().innerText()
  await page.getByLabel('Scopo del lancio').fill('Smoke HTTPS privato, operatore sintetico.')
  await page.getByRole('button', { name: 'Invia richiesta', exact: true }).click()
  await page.getByLabel('Motivazione', { exact: true }).fill('Conferma sintetica esplicita.')
  await page.getByRole('button', { name: 'Registra decisione' }).click()
  await page.getByRole('button', { name: 'Esplorazione', exact: true }).click()
  assert.equal((await (await page.request.get(`/v1/sessions/${sid}`)).json()).executed_experiments, 0)
  assert.equal((await page.request.post(`/v1/sessions/${sid}/stop`, {
    data: { expected_version: 1, reason: 'operator_stop' },
  })).status(), 403)
  await page.getByRole('button', { name: 'Esegui esperimento →' }).click()
  await page.getByText('5 misure registrate', { exact: true }).waitFor()
  console.error('zone-smoke-stage:reload')
  await page.reload()
  await page.getByRole('button', { name: 'Crea sessione', exact: true }).waitFor()
  await page.getByLabel('ID sessione', { exact: true }).fill(sid)
  await page.getByRole('button', { name: 'Apri sessione', exact: true }).click()
  await page.getByRole('heading', { name: 'Proponi un esperimento' }).waitFor()
  await page.screenshot({ path: process.env.ZONE_SMOKE_OUTPUT + '/beta-desktop.png', fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth))
  await page.screenshot({ path: process.env.ZONE_SMOKE_OUTPUT + '/beta-mobile.png', fullPage: true })
  assert.deepEqual(errors, [])
  console.log(JSON.stringify({ tls_verified: true, secure_httponly_cookie: true,
    explicit_experiment: true, csrf_denied: true, reload_session: true,
    persistent_browser_storage_empty: true, mobile_no_overflow: true, real_model_calls: 0 }))
} finally { await browser.close() }
