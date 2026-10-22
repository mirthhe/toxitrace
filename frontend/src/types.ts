// Mirrors backend/app/schemas.py. Keep the two in sync.

export type Severity = 'info' | 'caution' | 'conflict'
export type TraceStatus = 'ok' | 'not_found' | 'error' | 'timeout' | 'rate_limited'

export interface Flag {
  rule_id: string
  severity: Severity
  message: string
  refs: string[]
}

export interface Candidate {
  name: string | null
  dtxsid: string | null
  cas: string | null
  inchikey: string | null
  smiles: string | null
  formula: string | null
}

export interface Identity {
  input: string
  input_type: 'cas' | 'smiles' | 'dtxsid' | 'name'
  status: 'resolved' | 'ambiguous' | 'not_found'
  name: string | null
  smiles: string | null
  inchikey: string | null
  formula: string | null
  dtxsid: string | null
  cas: string | null
  pubchem_cid: number | null
  in_dsstox: boolean
  candidates: Candidate[]
}

export interface TraceEntry {
  ref: string
  source: string
  tool: string
  status: TraceStatus
  request: Record<string, unknown>
  response: unknown
  error: string | null
  duration_ms: number | null
  retrieved_at: string
}

export interface AnalysisResult {
  chemical_input: string
  endpoint: string
  identity: Identity | null
  flags: Flag[]
  trace: TraceEntry[]
}

export interface Health {
  status: string
  mode: 'live' | 'offline'
  demo_inputs: string[]
  toxindex_key_configured: boolean
}
