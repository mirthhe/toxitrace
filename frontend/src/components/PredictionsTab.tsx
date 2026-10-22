import type { AnalysisResult, Prediction } from '../types'
import { CallBadge } from './CallBadge'
import { RefChip } from './RefChip'

const APPLICABILITY: Record<Prediction['applicability'], string> = {
  in_domain: 'In domain',
  outside_domain: 'Outside domain',
  not_reported: 'Not reported',
}

export function PredictionsTab({ result }: { result: AnalysisResult }) {
  const { predictions, upstream_verdict: upstream } = result
  return (
    <div className="tab-body">
      <p className="muted">
        Model and rule-based calls. These are predictions, not measurements <span className="rule">R2</span>.
      </p>
      {predictions.length === 0 ? (
        <p className="muted">No predictions were obtained.</p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Source</th>
                <th>Call</th>
                <th>Score or detail</th>
                <th>Applicability</th>
                <th>Trace</th>
              </tr>
            </thead>
            <tbody>
              {predictions.map((p, i) => (
                <tr key={i}>
                  <td>
                    <strong>{p.source}</strong>
                    <div className="muted small">{p.assay}</div>
                  </td>
                  <td>
                    <CallBadge call={p.call} />
                  </td>
                  <td>
                    {p.probability != null && (
                      <ProbabilityBar probability={p.probability} threshold={p.threshold ?? 0.5} />
                    )}
                    {p.probability == null && <span className="small">{p.detail}</span>}
                    {p.confidence && <div className="muted small">Upstream confidence: {p.confidence}</div>}
                  </td>
                  <td>
                    <span className={`applicability applicability-${p.applicability}`}>
                      {APPLICABILITY[p.applicability]}
                    </span>
                  </td>
                  <td>
                    <RefChip refId={p.tool_ref} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {upstream && (
        <div className="upstream">
          <h3>ToxIndex aggregate verdict</h3>
          <p>
            “{upstream.conclusion}” <RefChip refId={upstream.tool_ref} />
          </p>
          <p className="muted small">
            Basis: {upstream.basis ?? 'not stated'} · confidence: {upstream.confidence ?? 'not stated'}. Shown for
            transparency; ToxiTrace computes its own summary from the individual results.
          </p>
        </div>
      )}
    </div>
  )
}

function ProbabilityBar({ probability, threshold }: { probability: number; threshold: number }) {
  return (
    <div className="prob">
      <div className="prob-track" title={`P(Ames-positive) = ${probability}`}>
        <div className="prob-fill" style={{ width: `${probability * 100}%` }} />
        <div className="prob-threshold" style={{ left: `${threshold * 100}%` }} />
      </div>
      <span className="mono small">P = {probability.toPrecision(3)}</span>
    </div>
  )
}
