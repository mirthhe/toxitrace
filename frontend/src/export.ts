import type { AnalysisResult, Health } from './types'

/** Download the full result, trace included, so an analysis can be archived and re-checked. */
export function downloadJson(result: AnalysisResult, health: Health | null) {
  const report = {
    exported_at: new Date().toISOString(),
    tool: 'ToxiTrace',
    mode: health?.mode ?? 'unknown', // "offline" means recorded responses, not live calls
    result,
  }
  const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  const safeName = result.chemical_input.replace(/[^A-Za-z0-9-]+/g, '_').slice(0, 40)
  link.href = url
  link.download = `toxitrace_${safeName}_${new Date().toISOString().slice(0, 10)}.json`
  link.click()
  URL.revokeObjectURL(url)
}
