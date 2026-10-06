// Deliberately narrow AST lint; tsc separately checks types and unused symbols.
import ts from 'typescript'
import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { pathToFileURL } from 'node:url'

export function lintSource(source, name = 'source.tsx') {
  const file = ts.createSourceFile(name, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const problems = []
  function visit(node) {
    if (ts.isIdentifier(node) && ['eval', 'Function', 'localStorage', 'sessionStorage', 'dangerouslySetInnerHTML', 'innerHTML'].includes(node.text)) {
      const { line } = file.getLineAndCharacterOfPosition(node.getStart(file))
      problems.push(`${name}:${line + 1}: ${node.text} non consentito nel client pubblico`)
    }
    ts.forEachChild(node, visit)
  }
  visit(file)
  return problems
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  function check(dir) {
    return readdirSync(dir, { withFileTypes: true }).flatMap(entry => {
      const path = join(dir, entry.name)
      if (entry.isDirectory()) return check(path)
      return /\.tsx?$/.test(path) ? lintSource(readFileSync(path, 'utf8'), path) : []
    })
  }
  const problems = check('src')
  if (problems.length) { console.error(problems.join('\n')); process.exitCode = 1 }
  else console.log('Lint AST frontend: nessuna esecuzione dinamica, HTML raw o storage persistente.')
}
