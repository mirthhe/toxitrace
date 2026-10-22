import type { Flag, Severity } from './types'

export const SEVERITY_ORDER: Severity[] = ['conflict', 'caution', 'info']

export function countBySeverity(flags: Flag[]): Record<Severity, number> {
  const counts = { conflict: 0, caution: 0, info: 0 }
  for (const f of flags) counts[f.severity] += 1
  return counts
}
