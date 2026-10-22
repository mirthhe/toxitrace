import type { AnalysisResult } from '../types'
import { RefChip } from './RefChip'
import { TkSection } from './TkSection'

export function ContextTab({ result }: { result: AnalysisResult }) {
  const reg = result.regulatory
  return (
    <div className="tab-body">
      <h3>
        Regulatory context <span className="rule">R8</span>
      </h3>
      {!reg ? (
        <p className="muted">Not assessed.</p>
      ) : !reg.n_nitroso ? (
        <p className="muted">Not an N-nitroso compound; no nitrosamine-specific context applies.</p>
      ) : (
        <>
          <p>
            N-nitroso compound: part of the ICH M7 “cohort of concern”. For nitrosamines, an enhanced Ames protocol is
            recommended because the standard protocol can under-detect them.
          </p>
          {reg.ema ? (
            <dl className="stat-grid">
              <Stat label="CPCA category" value={reg.ema.cpca_category ?? '—'} />
              <Stat
                label="Acceptable intake"
                value={reg.ema.ai_ng_per_day != null ? `${reg.ema.ai_ng_per_day} ng/day` : '—'}
              />
              <Stat label="Listed as" value={reg.ema.name} />
              <Stat label="Published" value={reg.ema.publication_date ?? '—'} />
            </dl>
          ) : (
            <p className="muted">Not on the EMA nitrosamine acceptable-intake list.</p>
          )}
          <p className="muted small">
            Source: EMA, Appendix 1 to the nitrosamine Q&amp;A{reg.ema?.revision ? ` (${reg.ema.revision})` : ''}{' '}
            <RefChip refId={reg.tool_ref} />
          </p>
        </>
      )}

      <TkSection tk={result.toxicokinetics} />
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="stat">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  )
}
