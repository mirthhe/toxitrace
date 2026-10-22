import { SEVERITY_ORDER } from '../flags'
import type { AnalysisResult, Flag, Identity } from '../types'
import { RefChips } from './RefChip'

export function OverviewTab({ result }: { result: AnalysisResult }) {
  const sorted = [...result.flags].sort((a, b) => SEVERITY_ORDER.indexOf(a.severity) - SEVERITY_ORDER.indexOf(b.severity))
  return (
    <div className="tab-body">
      <h3>Flags</h3>
      <p className="muted">
        Each flag comes from one rule in <code>docs/plan.md</code> and cites the calls it is based on.
      </p>
      {sorted.length === 0 ? <p className="muted">No flags raised.</p> : <FlagList flags={sorted} />}

      {result.identity && <IdentityDetails identity={result.identity} />}

      {result.limitations.length > 0 && (
        <>
          <h3>Limitations</h3>
          <ul className="limitations">
            {result.limitations.map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}

function FlagList({ flags }: { flags: Flag[] }) {
  return (
    <ul className="flags">
      {flags.map((f, i) => (
        <li key={i} className={`flag flag-${f.severity}`}>
          <span className={`badge badge-${f.severity}`}>{f.severity}</span>
          <span className="rule">{f.rule_id}</span>
          <span className="flag-message">{f.message}</span>
          <RefChips refs={f.refs} />
        </li>
      ))}
    </ul>
  )
}

function IdentityDetails({ identity }: { identity: Identity }) {
  return (
    <>
      <h3>
        Identity <span className="rule">R1</span>
      </h3>
      <p className="muted">
        Input read as {identity.input_type.toUpperCase()}: <code>{identity.input}</code>
      </p>
      {identity.status === 'resolved' && (
        <dl className="facts">
          <Fact label="Name" value={identity.name} />
          <Fact label="SMILES" value={identity.smiles} mono />
          <Fact label="InChIKey" value={identity.inchikey} mono />
          <Fact label="Formula" value={identity.formula} />
          <Fact label="CAS" value={identity.cas} />
          <Fact label="EPA DSSTox" value={identity.dtxsid ?? 'not in registry'} />
          <Fact label="PubChem CID" value={identity.pubchem_cid?.toString() ?? null} />
        </dl>
      )}
      {identity.status === 'ambiguous' && (
        <table className="table">
          <thead>
            <tr>
              <th>Name</th>
              <th>DTXSID</th>
              <th>CAS</th>
              <th>InChIKey</th>
            </tr>
          </thead>
          <tbody>
            {identity.candidates.map((c) => (
              <tr key={c.dtxsid ?? c.inchikey ?? c.name}>
                <td>{c.name}</td>
                <td className="mono">{c.dtxsid}</td>
                <td>{c.cas}</td>
                <td className="mono">{c.inchikey}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  )
}

function Fact({ label, value, mono }: { label: string; value: string | null; mono?: boolean }) {
  return (
    <>
      <dt>{label}</dt>
      <dd className={mono ? 'mono' : undefined}>{value ?? <span className="muted">unknown</span>}</dd>
    </>
  )
}
