import { readdirSync, readFileSync, lstatSync } from 'node:fs'
import { join, extname } from 'node:path'
import { pathToFileURL } from 'node:url'

const extensions = new Set(['.html', '.css', '.js', '.svg', '.png', '.ico', '.woff', '.woff2'])
// Environment variable names are public instructions; their values are secrets.
const forbidden = ['probe_truth', 'secret_grid', 'generator_seed', 'PRIVATE_LAW_SENTINEL', 'PRIVATE_TOKEN_SENTINEL', 'benchmark_private/']
export function bundleProblems(path, contents) {
  const problems = []
  if (!extensions.has(extname(path).toLowerCase())) problems.push(`${path}: file non compilato/pubblico`)
  if (/\.(html|css|js|svg)$/.test(path)) {
    for (const word of forbidden) if (contents.includes(word)) problems.push(`${path}: campo privato ${word}`)
    if (/\bsk-(?:proj-)?[a-zA-Z0-9_-]{20,}/.test(contents)) problems.push(`${path}: possibile credenziale`)
  }
  return problems
}
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  function check(dir) {
    return readdirSync(dir, { withFileTypes: true }).flatMap(entry => {
      const path = join(dir, entry.name)
      if (lstatSync(path).isSymbolicLink()) return [`${path}: symlink rifiutato`]
      return entry.isDirectory() ? check(path) : bundleProblems(path, readFileSync(path, 'utf8'))
    })
  }
  const problems = check('dist')
  if (problems.length) { console.error(problems.join('\n')); process.exitCode = 1 }
  else console.log('Bundle pubblico verificato (scansione euristica; non certifica testi arbitrari).')
}
