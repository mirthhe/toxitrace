import { useEffect, useRef } from 'react'
import type { TraceEntry } from '../types'

const SOURCE_LABELS: Record<string, string> = {
  toxindex: 'ToxIndex',
  pubchem: 'PubChem',
  local: 'Local (RDKit)',
}

export function TraceTab({ entries, highlight }: { entries: TraceEntry[]; highlight: string | null }) {
  const highlighted = useRef<HTMLDetailsElement>(null)

  useEffect(() => {
    highlighted.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, [highlight])

  return (
    <div className="tab-body">
      <p className="muted">
        Every external call and local computation behind this result, in order. Requests never contain credentials.
      </p>
      {entries.map((e) => (
        <details
          key={e.ref}
          id={`trace-${e.ref}`}
          ref={e.ref === highlight ? highlighted : undefined}
          className={`trace-entry${e.ref === highlight ? ' highlighted' : ''}`}
          open={e.ref === highlight}
        >
          <summary>
            <code className="trace-ref">{e.ref}</code>
            <span className="trace-source">{SOURCE_LABELS[e.source] ?? e.source}</span>
            <span>{e.tool}</span>
            <span className={`badge badge-${e.status === 'ok' ? 'info' : 'caution'}`}>{e.status}</span>
            {e.duration_ms != null && <span className="muted">{e.duration_ms} ms</span>}
          </summary>
          {e.error && <p className="alert">{e.error}</p>}
          <div className="trace-io">
            <div>
              <h4>Request</h4>
              <pre>{JSON.stringify(e.request, null, 2)}</pre>
            </div>
            <div>
              <h4>Response</h4>
              <pre>{e.response == null ? '—' : JSON.stringify(e.response, null, 2)}</pre>
            </div>
          </div>
          <p className="muted small">Retrieved {new Date(e.retrieved_at).toLocaleString()}</p>
        </details>
      ))}
    </div>
  )
}
