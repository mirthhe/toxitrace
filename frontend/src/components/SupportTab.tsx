import type { AnalysisResult, Neighbour } from '../types'
import { CallBadge } from './CallBadge'
import { RefChip } from './RefChip'
import { Structure } from './Structure'
import { RuleChip } from './RulesGuide'

const THRESHOLD = 0.4 // docs/plan.md §7

const SPLITS: Record<string, string> = {
  train: 'train (Hansen/ISSSTY)',
  test: 'test (Hansen/ISSSTY)',
  validation: 'external validation',
}

export function SupportTab({ result }: { result: AnalysisResult }) {
  const support = result.structural_support
  if (!support) {
    return (
      <div className="tab-body">
        <p className="muted">
          No structural comparison was made: the local reference data is not installed (see the README setup steps).
        </p>
      </div>
    )
  }
  return (
    <div className="tab-body">
      <p className="muted">
        Measured compounds closest to this structure in {support.dataset}, by {support.fingerprint}{' '}
        <RefChip refId={support.tool_ref} />. Similarities below {THRESHOLD} count as low support <RuleChip id="R6" />.
      </p>

      <h3>
        This substance itself <RuleChip id="R5" />
      </h3>
      {support.exact_match ? (
        <p>
          Measured <CallBadge call={support.exact_match.call} /> in the {SPLITS[support.exact_match.split]} split.{' '}
          {support.exact_match.split !== 'validation' &&
            'The prediction model was trained on this data, so agreement with it is expected.'}
        </p>
      ) : (
        <p className="muted">Not in the dataset (matched by InChIKey).</p>
      )}

      <h3>Nearest measured analogues</h3>
      <div className="neighbours">
        {support.neighbours.map((n) => (
          <NeighbourCard key={n.inchikey} neighbour={n} />
        ))}
      </div>
    </div>
  )
}

function NeighbourCard({ neighbour: n }: { neighbour: Neighbour }) {
  const low = n.similarity < THRESHOLD
  return (
    <figure className={`neighbour${low ? ' low' : ''}`}>
      <Structure smiles={n.smiles} alt={n.smiles} width={220} height={140} />
      <figcaption>
        <div className="neighbour-sim">
          <div className="sim-track">
            <div className="sim-fill" style={{ width: `${n.similarity * 100}%` }} />
          </div>
          <span className="mono small">{n.similarity.toFixed(2)}</span>
        </div>
        <div className="neighbour-meta">
          <CallBadge call={n.call} />
          <span className="muted small">{SPLITS[n.split] ?? n.split}</span>
        </div>
        <code className="neighbour-smiles" title={n.inchikey}>
          {n.smiles}
        </code>
      </figcaption>
    </figure>
  )
}
