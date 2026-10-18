import { useEffect, useRef } from 'react'
import katex from 'katex'

// Render-only boundary: never evaluate formulas, share macros, or trust model HTML/URLs.
export function Formula({ source, display = false }: { source: string; display?: boolean }) {
  const ref = useRef<HTMLSpanElement>(null)
  useEffect(() => {
    if (!ref.current) return
    try {
      if (source.length > 2000) throw new Error('Formula troppo lunga')
      // Native MathML avoids inline styles and works with the server's strict CSP.
      katex.render(source, ref.current, { displayMode: display, output: 'mathml', trust: false,
        strict: 'error', throwOnError: true, maxSize: 8, maxExpand: 100, macros: {} })
    } catch { ref.current.textContent = source }
  }, [source, display])
  return <span className={display ? 'formula display-formula' : 'formula'} ref={ref} />
}

export function ScientificText({ text }: { text: string }) {
  const parts = text.split(/(\$\$[\s\S]+?\$\$|\\\[[\s\S]+?\\\]|\\\([\s\S]+?\\\)|(?<!\\)\$[^$\n]+?\$)/g)
  return <span className="scientific-text">{parts.map((part, i) => {
    const display = part.startsWith('$$') || part.startsWith('\\[')
    const math = display || part.startsWith('\\(') || part.startsWith('$') && part.endsWith('$')
    return math ? <Formula key={i} source={part.slice(display || part.startsWith('\\(') ? 2 : 1, display || part.startsWith('\\(') ? -2 : -1)} display={display} /> : <span key={i}>{part}</span>
  })}</span>
}
