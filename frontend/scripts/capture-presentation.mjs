// Local product captures and a silent English introduction. No model calls.
// Requires a fresh loopback workspace, Playwright and FFmpeg on PATH.
import assert from 'node:assert/strict'
import { mkdirSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { execFileSync } from 'node:child_process'
import { chromium } from 'playwright'

const baseURL = process.env.ZONE_SMOKE_BASE_URL || 'http://127.0.0.1:8770'
assert(/^http:\/\/127\.0\.0\.1:\d+$/.test(baseURL), 'Use a local preview only.')
const out = resolve(process.env.ZONE_MEDIA_OUT || '../benchmark_data/english-presentation')
mkdirSync(out, { recursive: true })
const browser = await chromium.launch({ ...(process.platform === 'win32' ? { channel: 'msedge' } : {}), headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, baseURL, reducedMotion: 'reduce' })
try {
  await context.route('**/*', route => new URL(route.request().url()).origin === baseURL ? route.continue() : route.abort())
  if (!process.argv.includes('--reuse-captures')) {
  const page = await context.newPage()
  await page.goto('/')
  assert.equal(await page.locator('html').getAttribute('lang'), 'en')
  await page.getByText('Try a demo, no account or AI needed', { exact: true }).click()
  await page.locator('.landing-demo').getByLabel('Observed sample').fill('2')
  await page.screenshot({ path: `${out}/landing.png`, fullPage: true })
  await page.locator('.landing-demo .experiment-stage').screenshot({ path: `${out}/demo.png` })
  await page.getByLabel('Username', { exact: true }).fill(`demo_${Date.now().toString(36)}`)
  await page.getByLabel('Password', { exact: true }).fill('synthetic-presentation-password-123')
  await page.getByRole('button', { name: 'Create account and continue', exact: true }).click()
  await page.getByLabel('Recovery code').waitFor()
  // Never photograph the recovery screen, passwords, keys or any private record.
  await page.getByRole('button', { name: 'I have saved my code', exact: true }).click()
  await page.locator('.mode-directory').screenshot({ path: `${out}/modes.png` })
  await page.getByRole('button', { name: 'AI connections', exact: true }).click()
  await page.getByRole('heading', { name: 'Add a connection', exact: true }).waitFor()
  await page.locator('.connection-layout').screenshot({ path: `${out}/connections.png` })
  await page.getByRole('button', { name: 'Explore modes', exact: true }).click()
  await page.locator('.mode-entry').filter({ hasText: 'Watch an Agent' }).click()
  await page.getByRole('button', { name: 'Create investigation', exact: true }).click()
  for (let i = 0; i < 3; i++) {
    await page.getByRole('button', { name: 'Ask for next step', exact: true }).click()
    await page.locator('.lab-activity').waitFor({ state: 'hidden' })
    if (await page.getByRole('heading', { name: 'Review the proposal', exact: true }).count()) break
  }
  const decision = page.locator('.panel').filter({ has: page.getByRole('heading', { name: 'Review the proposal', exact: true }) })
  await decision.screenshot({ path: `${out}/approval.png` })
  await decision.getByLabel('Reason', { exact: true }).fill('Gather the first public measurements.')
  await decision.getByRole('button', { name: 'Save decision', exact: true }).click()
  await page.getByRole('button', { name: 'Exploration', exact: true }).click()
  await page.getByRole('button', { name: 'Run experiment', exact: true }).click()
  await page.locator('.public-experiment .sample-point').first().waitFor()
  await page.locator('.public-experiment').getByLabel('Observed sample').fill('2')
  await page.locator('.public-experiment').screenshot({ path: `${out}/measurements.png` })
  await page.getByRole('button', { name: 'Ask for next step', exact: true }).click()
  await page.locator('.lab-activity').waitFor({ state: 'hidden' })
  await page.locator('.event-card').filter({ has: page.getByRole('heading', { name: 'Hypothesis', exact: true }) }).last().screenshot({ path: `${out}/hypothesis.png` })
  }

  const image = name => `data:image/png;base64,${readFileSync(`${out}/${name}.png`).toString('base64')}`
  const slides = [
    ['Discover the rules.', 'Zone is a laboratory of unknown universes. Ask questions, design experiments and show the evidence.', 'demo', 'Illustrative samples · not evaluation evidence'],
    ['Choose your investigation.', 'Explore for yourself, guide an agent, compare predictions or build a universe.', 'modes', 'Six modes · one scientific workflow'],
    ['You decide what runs.', 'The agent proposes. You approve, modify or reject. A separate command runs the experiment.', 'approval', 'Actual application · numerical offline baseline'],
    ['Learn from measurements.', 'Observe motion. Record a hypothesis. Preregister a prediction before testing it.', 'measurements', 'Actual local simulator · public observations only'],
    ['Bring your own AI.', 'Personal APIs, ChatGPT through a local connector, or an installed Ollama model. You choose the model.', 'connections', 'Provider eligibility and costs depend on your account'],
    ['Make it your laboratory.', 'Open source. MIT licensed. Runs on your computer or server. Start without an AI key.', 'modes', 'github.com/zalaso/Zone'],
  ]
  const poster = await context.newPage()
  await poster.setViewportSize({ width: 1920, height: 1080 })
  for (const [i, [title, copy, shot, note]] of slides.entries()) {
    // Authored presentation, separate from the application; captures are unedited.
    await poster.setContent(`<!doctype html><html lang="en"><meta charset="utf-8"><title>Zone introduction</title><style>
      *{box-sizing:border-box}body{margin:0;background:#f7f9fc;color:#182534;font-family:Arial,sans-serif;width:1920px;height:1080px;overflow:hidden}
      header{position:absolute;top:60px;left:90px;right:90px;display:flex;justify-content:space-between;align-items:center;font-size:25px;color:#526274}
      .brand{font-size:46px;font-weight:700;letter-spacing:-2px;color:#215ca5}.layout{position:absolute;left:90px;right:90px;top:205px;bottom:125px;display:grid;grid-template-columns:580px 1fr;gap:75px;align-items:center}
      h1{font-size:76px;line-height:1.06;letter-spacing:-3px;margin:0 0 35px;font-weight:650}p{font-size:31px;line-height:1.55;color:#526274;margin:0}
      .screen{height:750px;min-width:0;min-height:0;display:flex;align-items:center;justify-content:center}img{display:block;width:auto;height:auto;max-width:100%;max-height:750px;object-fit:contain;border:1px solid #d5dfea;border-radius:12px;box-shadow:0 16px 48px #10253c0c;background:white}
      footer{position:absolute;bottom:60px;left:90px;right:90px;border-top:1px solid #d5dfea;padding-top:23px;font-size:23px;display:flex;justify-content:space-between;color:#526274}footer span:last-child{color:#215ca5}
      </style><header><span class="brand">zone</span><span>Your laboratory. Your AI.</span></header><main class="layout"><div><h1>${title}</h1><p>${copy}</p></div><div class="screen"><img alt="English Zone application" src="${image(shot)}"></div></main><footer><span>${note}</span><span>${i === 5 ? 'Install → investigate → test' : 'A laboratory of unknown universes'}</span></footer></html>`)
    await poster.locator('img').evaluate(img => img.decode())
    await poster.screenshot({ path: `${out}/slide-${i + 1}.png` })
  }
  const ffmpeg = process.env.ZONE_FFMPEG || 'ffmpeg'
  // One encoding context keeps codec parameters consistent across all six scenes.
  const inputs = slides.flatMap((_, i) => ['-loop', '1', '-framerate', '24', '-t', '7', '-i', `${out}/slide-${i + 1}.png`])
  const filters = slides.map((_, i) => `[${i}:v]setpts=PTS-STARTPTS,setsar=1,fade=t=in:st=0:d=0.25,fade=t=out:st=6.75:d=0.25,format=yuv420p[v${i}]`)
  filters.push(`${slides.map((_, i) => `[v${i}]`).join('')}concat=n=${slides.length}:v=1:a=0[video]`)
  execFileSync(ffmpeg, ['-y', '-loglevel', 'error', ...inputs, '-filter_complex', filters.join(';'), '-map', '[video]', '-c:v', 'libx264', '-preset', 'fast', '-crf', '21', '-an', '-movflags', '+faststart', `${out}/zone-introduction-en.mp4`], { stdio: 'inherit' })
  console.log(`English screenshots and 42-second 1080p MP4 saved to ${out}. No provider calls.`)
} finally { await browser.close() }
