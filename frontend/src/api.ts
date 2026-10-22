import type { AnalysisResult, Health } from './types'

async function errorMessage(resp: Response): Promise<string> {
  try {
    const body = await resp.json()
    if (typeof body.detail === 'string') return body.detail
    if (Array.isArray(body.detail)) return 'Enter a chemical name, CAS number, DTXSID or SMILES.'
  } catch {
    // fall through to the generic message
  }
  return `The server returned an error (HTTP ${resp.status}).`
}

export async function getHealth(): Promise<Health> {
  const resp = await fetch('/api/health')
  if (!resp.ok) throw new Error(await errorMessage(resp))
  return resp.json()
}

export async function analyze(chemicalInput: string): Promise<AnalysisResult> {
  const resp = await fetch('/api/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chemical_input: chemicalInput }),
  })
  if (!resp.ok) throw new Error(await errorMessage(resp))
  return resp.json()
}
