import { SEVERITY_ORDER, countBySeverity } from '../flags'
import type { AnalysisResult } from '../types'

export function SummaryHeader({ result }: { result: AnalysisResult }) {
  const identity = result.identity
  const counts = countBySeverity(result.flags)
  const resolved = identity?.status === 'resolved'

  return (
    <section className="summary card">
      <div className="structure">
        {resolved && identity.smiles ? (
          <img src={`/api/depict?smiles=${encodeURIComponent(identity.smiles)}`} alt={`Structure of ${identity.name ?? identity.smiles}`} />
        ) : (
          <span className="muted">No structure</span>
        )}
      </div>

      <div className="summary-body">
        <h2 className="chemical-name">{resolved ? (identity.name ?? identity.smiles) : identity?.input}</h2>
        {resolved && (
          <p className="ids">
            {[
              identity.cas && `CAS ${identity.cas}`,
              identity.dtxsid ?? 'not in EPA DSSTox',
              identity.pubchem_cid && `PubChem CID ${identity.pubchem_cid}`,
            ]
              .filter(Boolean)
              .join(' · ')}
          </p>
        )}

        <Verdict result={result} />

        <p className="flag-counts">
          {SEVERITY_ORDER.map((s) => (
            <span key={s} className={`badge badge-${s}`}>
              {counts[s]} {s}
            </span>
          ))}
        </p>
      </div>
    </section>
  )
}

function Verdict({ result }: { result: AnalysisResult }) {
  const status = result.identity?.status
  if (status === 'ambiguous') {
    return <div className="verdict verdict-caution">Ambiguous input: choose one substance below before analysing.</div>
  }
  if (status !== 'resolved') {
    return <div className="verdict verdict-caution">No analysis: the substance could not be identified.</div>
  }
  // The overall verdict is computed by rules R2–R9, which are not built yet.
  return (
    <div className="verdict verdict-pending">
      Verdict pending: the weight-of-evidence rules (R2–R9) are not built yet. Identity is established.
    </div>
  )
}
