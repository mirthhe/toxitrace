import { useGoToRef } from '../navigation'

/** A trace reference such as "toxindex-1": click to see the call it points to. */
export function RefChip({ refId }: { refId: string }) {
  const goToRef = useGoToRef()
  return (
    <button type="button" className="ref-chip" onClick={() => goToRef(refId)} title="Show this call in the trace">
      {refId}
    </button>
  )
}

export function RefChips({ refs }: { refs: string[] }) {
  if (refs.length === 0) return null
  return (
    <span className="ref-chips">
      {refs.map((r) => (
        <RefChip key={r} refId={r} />
      ))}
    </span>
  )
}
