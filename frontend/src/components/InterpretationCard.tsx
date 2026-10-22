import type { ReactNode } from 'react'
import { useGoToRef } from '../navigation'
import type { Check, Interpretation } from '../types'
import { RefChip } from './RefChip'

const TRACE_REF = /^[a-z]+-\d+$/
const RULE_ID = /^R\d+$/
const CITATION = /\s*\[([^\]]+)\]/g

/**
 * Replace "[toxindex-2, local-1]" citations by superscript numbers, numbered in order of first
 * use, and collect the trace refs they stand for. Rule ids (R3) are dropped from the text: the
 * verdict box already shows which rules it rests on.
 */
function numberCitations(text: string): { paragraphs: (string | { n: number; ref: string })[][]; refs: string[] } {
  const refs: string[] = []
  const paragraphs = text.split(/\n\s*\n/).map((para) => {
    const parts: (string | { n: number; ref: string })[] = []
    let last = 0
    for (const match of para.matchAll(CITATION)) {
      const items = match[1].split(',').map((s) => s.trim())
      if (!items.every((r) => TRACE_REF.test(r) || RULE_ID.test(r))) continue
      parts.push(para.slice(last, match.index))
      for (const ref of items.filter((r) => TRACE_REF.test(r))) {
        if (!refs.includes(ref)) refs.push(ref)
        parts.push({ n: refs.indexOf(ref) + 1, ref })
      }
      last = match.index + match[0].length
    }
    parts.push(para.slice(last))
    return parts
  })
  return { paragraphs, refs }
}

export function InterpretationCard({ interpretation, checks }: { interpretation: Interpretation; checks: Check[] }) {
  const goToRef = useGoToRef()
  const grounding = checks.find((c) => c.name === 'R10 grounding')
  const llm = interpretation.source === 'llm'
  const { paragraphs, refs } = numberCitations(interpretation.text)

  const render = (parts: (string | { n: number; ref: string })[]): ReactNode[] =>
    parts.map((p, i) =>
      typeof p === 'string' ? (
        p
      ) : (
        <sup key={i}>
          <button type="button" className="cite" onClick={() => goToRef(p.ref)} title={p.ref}>
            {p.n}
          </button>
        </sup>
      ),
    )

  return (
    <section className="interpretation">
      <h3>Interpretation</h3>
      {paragraphs.map((parts, i) => (
        <p key={i}>{render(parts)}</p>
      ))}

      {refs.length > 0 && (
        <ol className="sources">
          {refs.map((ref, i) => (
            <li key={ref}>
              <span className="source-n">{i + 1}</span>
              <RefChip refId={ref} />
            </li>
          ))}
        </ol>
      )}

      <details className="interpretation-meta">
        <summary>
          {llm ? 'AI-generated, checked against the analysis' : 'Standard text'}
          <span className="rule">R10</span>
        </summary>
        <ul>
          {llm && (
            <li>
              Written by {interpretation.model} from the computed results; the verdict itself is computed, not
              generated.
            </li>
          )}
          {interpretation.note && <li>{interpretation.note}</li>}
          {grounding?.detail && <li>Grounding check: {grounding.detail}.</li>}
          {interpretation.tool_ref && (
            <li>
              LLM call: <RefChip refId={interpretation.tool_ref} />
            </li>
          )}
        </ul>
      </details>
    </section>
  )
}
