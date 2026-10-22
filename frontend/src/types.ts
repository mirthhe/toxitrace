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

export type Call = 'positive' | 'negative' | 'equivocal' | 'unknown'

export interface Prediction {
  source: string
  call: Call
  assay: string
  probability: number | null
  threshold: number | null
  confidence: string | null
  applicability: 'in_domain' | 'outside_domain' | 'not_reported'
  detail: string | null
  tool_ref: string
}

export interface Evidence {
  source: string
  method: 'experimental' | 'curated'
  call: Call
  assay: string
  system: string | null
  detail: string | null
  confidence: string | null
  tool_ref: string
}

export interface NotRetrieved {
  source: string
  reason: string
  tool_ref: string | null
}

export interface UpstreamVerdict {
  conclusion: string
  basis: string | null
  confidence: string | null
  mechanism: string | null
  tool_ref: string
}

export interface Neighbour {
  smiles: string
  inchikey: string
  call: Call
  split: string
  similarity: number
}

export interface StructuralSupport {
  dataset: string
  fingerprint: string
  exact_match: Neighbour | null
  neighbours: Neighbour[]
  tool_ref: string
}

export interface EmaEntry {
  name: string
  cpca_category: string | null
  ai_ng_per_day: number | null
  publication_date: string | null
  revision: string | null
}

export interface RegulatoryContext {
  n_nitroso: boolean
  ema: EmaEntry | null
  tool_ref: string
}

export interface HalfLife {
  species: string
  sex: string
  hours: number
  reference: string | null
}

export interface TkContext {
  status: 'half_lives' | 'parameters_only' | 'no_human_parameters' | 'not_in_httk' | 'not_assessed'
  compound: string | null
  clint_median: number | null
  clint_reference: string | null
  fup_median: number | null
  fup_reference: string | null
  half_lives: HalfLife[]
  source: string | null
  tool_ref: string | null
}

export type SummaryLabel = 'supported_positive' | 'supported_negative' | 'conflicting' | 'prediction_only' | 'insufficient'

export interface Summary {
  label: SummaryLabel
  text: string
  basis: string[]
}

export interface Interpretation {
  text: string
  source: 'llm' | 'template'
  model: string | null
  tool_ref: string | null
  note: string | null
}

export interface Check {
  name: string
  status: 'passed' | 'failed' | 'not_run'
  detail: string | null
}

export interface AnalysisResult {
  chemical_input: string
  endpoint: string
  identity: Identity | null
  summary: Summary | null
  flags: Flag[]
  predictions: Prediction[]
  evidence: Evidence[]
  not_retrieved: NotRetrieved[]
  upstream_verdict: UpstreamVerdict | null
  structural_support: StructuralSupport | null
  regulatory: RegulatoryContext | null
  toxicokinetics: TkContext | null
  interpretation: Interpretation | null
  checks: Check[]
  limitations: string[]
  trace: TraceEntry[]
}

export interface Health {
  status: string
  mode: 'live' | 'offline'
  demo_inputs: string[]
  toxindex_key_configured: boolean
  access_code_required: boolean
  access_code_rejected: boolean
}
