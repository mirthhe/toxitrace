import { useEffect, useRef, type MouseEvent } from 'react'
import { RULES } from '../rules'
import { useOpenRulesGuide } from '../rulesGuide'

/** A rule label (e.g. "R3"); click to read what the rule checks and why. */
export function RuleChip({ id }: { id: string }) {
  const openGuide = useOpenRulesGuide()
  const rule = RULES.find((r) => r.id === id)
  return (
    <button
      type="button"
      className="rule rule-button"
      title={rule ? `${rule.id}: ${rule.name}` : id}
      onClick={(e: MouseEvent) => {
        e.preventDefault() // also when inside a <summary>, which would otherwise toggle
        e.stopPropagation()
        openGuide(id)
      }}
    >
      {id}
    </button>
  )
}

/** Modal explaining the ten rules in plain language. */
export function RulesGuide({ focus, onClose }: { focus: string | null; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const el = dialog.current
    if (!el) return
    if (!el.open) el.showModal()
    if (focus) el.querySelector(`#rule-${focus}`)?.scrollIntoView({ block: 'center' })
  }, [focus])

  return (
    <dialog
      ref={dialog}
      className="rules-guide"
      aria-labelledby="rules-guide-title"
      onClose={onClose}
      onClick={(e) => e.target === dialog.current && dialog.current?.close()}
    >
      <div className="rules-guide-inner">
        <header className="rules-guide-head">
          <div>
            <h2 id="rules-guide-title">How ToxiTrace weighs the evidence</h2>
            <p className="muted">
              Ten rules run on every analysis. Each one raises flags that cite the calls they rest on. The verdict is
              computed from these flags, never generated.
            </p>
          </div>
          <button type="button" className="secondary" onClick={() => dialog.current?.close()}>
            Close
          </button>
        </header>
        <ol className="rules-list">
          {RULES.map((r) => (
            <li key={r.id} id={`rule-${r.id}`} className={r.id === focus ? 'focused' : undefined}>
              <div className="rules-list-head">
                <span className="rule">{r.id}</span>
                <h3>{r.name}</h3>
              </div>
              <p>
                <strong>Checks:</strong> {r.checks}
              </p>
              <p className="muted">
                <strong>Why:</strong> {r.why}
              </p>
            </li>
          ))}
        </ol>
        <p className="muted small">
          Technical details, inputs and test cases:{' '}
          <a href="https://github.com/mirthhe/toxitrace/blob/main/docs/plan.md">design plan in the repository</a>.
        </p>
      </div>
    </dialog>
  )
}
