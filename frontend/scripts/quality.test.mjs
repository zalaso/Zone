import { test } from 'node:test'
import assert from 'node:assert/strict'
import { bundleProblems } from './check-bundle.mjs'
import { lintSource } from './check-source.mjs'

test('AST lint rejects execution, persistent storage and raw HTML', () => {
  for (const source of ['eval(value)', 'new Function(value)', 'localStorage.setItem(key, token)', 'window.sessionStorage.clear()', '<div dangerouslySetInnerHTML={value} />', 'node.innerHTML = value']) assert(lintSource(source).length)
  assert.deepEqual(lintSource('const x = "eval localStorage"; // innerHTML\nconst view = <p>{x}</p>'), [])
})
test('bundle rejects private sentinels, credentials, maps and JSON', () => {
  for (const contents of ['probe_truth', 'secret_grid', 'generator_seed', 'PRIVATE_LAW_SENTINEL', 'PRIVATE_TOKEN_SENTINEL', 'sk-proj-syntheticfixture1234567890']) assert(bundleProblems('assets/app.js', contents).length)
  for (const path of ['world.json', 'app.js.map', '.env', 'app.tsx']) assert(bundleProblems(path, '{}').length)
  assert.deepEqual(bundleProblems('assets/app.js', 'const category = "interpolation"'), [])
  assert.deepEqual(bundleProblems('assets/app.js', 'const help = "Imposta ZONE_OPERATOR_TOKEN"'), [])
})
