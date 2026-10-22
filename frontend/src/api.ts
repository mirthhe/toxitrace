import type { AnalysisResult, Health } from './types'

const ACCESS_CODE_KEY = 'toxitrace-access-code'

// Remembered per browser; storage can be unavailable (private mode), so failures are ignored.
export function getAccessCode(): string | null {
  try {
    return localStorage.getItem(ACCESS_CODE_KEY)
  } catch {
    return null
  }
}

export function setAccessCode(code: string | null) {
  try {
    if (code) localStorage.setItem(ACCESS_CODE_KEY, code)
    else localStorage.removeItem(ACCESS_CODE_KEY)
  } catch {
    // ignore: the code then only lasts for this page view
  }
}

function headers(extra: Record<string, string> = {}): Record<string, string> {
  const code = getAccessCode()
  return code ? { ...extra, 'X-Access-Code': code } : extra
}

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
  const resp = await fetch('/api/health', { headers: headers() })
  if (!resp.ok) throw new Error(await errorMessage(resp))
  return resp.json()
}

export async function analyze(chemicalInput: string): Promise<AnalysisResult> {
  const resp = await fetch('/api/analyze', {
    method: 'POST',
    headers: headers({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ chemical_input: chemicalInput }),
  })
  if (!resp.ok) throw new Error(await errorMessage(resp))
  return resp.json()
}
