import type { AnalysisResult, Call } from '../types'
import { CallBadge } from './CallBadge'
import { RefChip } from './RefChip'
import { RuleChip } from './RulesGuide'

const COLUMNS: { call: Call; label: string }[] = [
  { call: 'positive', label: 'Positive' },
  { call: 'negative', label: 'Negative' },
  { call: 'equivocal', label: 'Equivocal' },
  { call: 'unknown', label: 'Unknown' },
]

interface Row {
  source: string
  detail: string
  call: Call | null // null: not retrieved
  ref: string | null
}

export function EvidenceTab({ result }: { result: AnalysisResult }) {
  const observed: Row[] = result.evidence.map((e) => ({
    source: e.source,
    detail: `${e.method} · ${e.assay}${e.system ? ` · ${e.system}` : ''}`,
    call: e.call,
    ref: e.tool_ref,
  }))
  const predicted: Row[] = result.predictions.map((p) => ({
    source: p.source,
    detail: `predicted · ${p.assay}`,
    call: p.call,
    ref: p.tool_ref,
  }))
  const missing: Row[] = result.not_retrieved.map((n) => ({
    source: n.source,
    detail: n.reason,
    call: null,
    ref: n.tool_ref,
  }))

  return (
    <div className="tab-body">
      <p className="muted">
        Every source at a glance. Measurements and predictions are kept in separate groups <RuleChip id="R2" />; sources
        that returned nothing are listed as not retrieved <RuleChip id="R7" />.
      </p>
      <div className="table-wrap">
        <table className="table matrix">
          <thead>
            <tr>
              <th>Source</th>
              {COLUMNS.map((c) => (
                <th key={c.call} className="matrix-col">
                  {c.label}
                </th>
              ))}
              <th className="matrix-col">Not retrieved</th>
              <th>Trace</th>
            </tr>
          </thead>
          <MatrixGroup title="Experimental and curated" rows={observed} empty="No experimental results retrieved." />
          <MatrixGroup title="Predicted" rows={predicted} empty="No predictions obtained." />
          {missing.length > 0 && <MatrixGroup title="Not retrieved" rows={missing} empty="" />}
        </table>
      </div>
      <p className="muted small">
        “Not retrieved” means this analysis obtained no result from that source. It does not mean the substance was
        never tested, or that it is not mutagenic.
      </p>
    </div>
  )
}

function MatrixGroup({ title, rows, empty }: { title: string; rows: Row[]; empty: string }) {
  return (
    <tbody>
      <tr className="matrix-group">
        <th colSpan={COLUMNS.length + 3}>{title}</th>
      </tr>
      {rows.length === 0 && (
        <tr>
          <td colSpan={COLUMNS.length + 3} className="muted small">
            {empty}
          </td>
        </tr>
      )}
      {rows.map((r, i) => (
        <tr key={i}>
          <td>
            <strong>{r.source}</strong>
            <div className="muted small">{r.detail}</div>
          </td>
          {COLUMNS.map((c) => (
            <td key={c.call} className="matrix-col">
              {r.call === c.call && <CallBadge call={c.call} />}
            </td>
          ))}
          <td className="matrix-col">{r.call === null && <span className="dash">—</span>}</td>
          <td>{r.ref && <RefChip refId={r.ref} />}</td>
        </tr>
      ))}
    </tbody>
  )
}
