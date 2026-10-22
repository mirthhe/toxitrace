import type { Call } from '../types'

const LABELS: Record<Call, string> = {
  positive: 'Positive',
  negative: 'Negative',
  equivocal: 'Equivocal',
  unknown: 'Unknown',
}

/** An Ames call. Colours encode the result, distinct from flag severities. */
export function CallBadge({ call }: { call: Call }) {
  return <span className={`call call-${call}`}>{LABELS[call]}</span>
}
