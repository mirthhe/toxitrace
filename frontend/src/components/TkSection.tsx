import type { HalfLife, TkContext } from '../types'
import { RefChip } from './RefChip'
import { RuleChip } from './RulesGuide'

const STATUS_TEXT: Record<TkContext['status'], string> = {
  half_lives: '',
  parameters_only: 'httk has human in vitro parameters but no measured half-life; no simulation is run here.',
  no_human_parameters: 'httk lists this substance but has no human in vitro toxicokinetic parameters.',
  not_in_httk: 'This substance is not in httk.',
  not_assessed: 'Not assessed: httk is keyed on DTXSID, and this substance is not in EPA DSSTox.',
}

// Log-scale axis from 1 hour to ~11 years.
const AXIS_MAX_HOURS = 1e5
const TICKS = [
  { hours: 1, label: '1 h' },
  { hours: 24, label: '1 day' },
  { hours: 168, label: '1 week' },
  { hours: 720, label: '1 month' },
  { hours: 8760, label: '1 year' },
]

function position(hours: number): number {
  const clamped = Math.min(Math.max(hours, 1), AXIS_MAX_HOURS)
  return (Math.log10(clamped) / Math.log10(AXIS_MAX_HOURS)) * 100
}

function duration(hours: number): string {
  if (hours >= 24 * 365) return `${(hours / (24 * 365)).toFixed(1)} years`
  if (hours >= 48) return `${Math.round(hours / 24)} days`
  return `${hours.toPrecision(3)} h`
}

export function TkSection({ tk }: { tk: TkContext | null }) {
  return (
    <>
      <h3>
        Toxicokinetic context <RuleChip id="R9" />
      </h3>
      {!tk ? (
        <p className="muted">Not assessed.</p>
      ) : (
        <>
          {tk.status === 'half_lives' ? (
            <HalfLifeChart halfLives={tk.half_lives} />
          ) : (
            <p className="muted">{STATUS_TEXT[tk.status]}</p>
          )}
          {(tk.clint_median != null || tk.fup_median != null) && (
            <dl className="stat-grid">
              {tk.clint_median != null && (
                <div className="stat">
                  <dt>Human hepatic clearance (Clint)</dt>
                  <dd>{tk.clint_median} µL/min/10⁶ cells</dd>
                  {tk.clint_reference && <span className="muted small">{tk.clint_reference}</span>}
                </div>
              )}
              {tk.fup_median != null && (
                <div className="stat">
                  <dt>Fraction unbound in plasma</dt>
                  <dd>{tk.fup_median}</dd>
                  {tk.fup_reference && <span className="muted small">{tk.fup_reference}</span>}
                </div>
              )}
            </dl>
          )}
          <p className="muted small">
            Source: {tk.source ?? 'httk'}. Context only: toxicokinetics does not change the Ames verdict.{' '}
            {tk.tool_ref && <RefChip refId={tk.tool_ref} />}
          </p>
        </>
      )}
    </>
  )
}

function HalfLifeChart({ halfLives }: { halfLives: HalfLife[] }) {
  const species = [...new Set(halfLives.map((h) => h.species))].sort((a, b) => {
    const max = (s: string) => Math.max(...halfLives.filter((h) => h.species === s).map((h) => h.hours))
    return max(b) - max(a)
  })
  return (
    <figure className="hl-chart">
      <figcaption className="muted small">Measured elimination half-life, by species and sex (log scale)</figcaption>
      {species.map((s) => (
        <div key={s} className="hl-row">
          <span className="hl-species">{s}</span>
          <div className="hl-bars">
            {halfLives
              .filter((h) => h.species === s)
              .map((h) => (
                <div key={h.sex} className="hl-bar-line" title={h.reference ?? undefined}>
                  <div
                    className={`hl-bar hl-${h.sex.toLowerCase()}${s === 'Human' ? ' hl-human' : ''}`}
                    style={{ width: `${position(h.hours)}%` }}
                  />
                  <span className="hl-value">
                    {h.sex === 'Female' ? '♀' : '♂'} {duration(h.hours)}
                  </span>
                </div>
              ))}
          </div>
        </div>
      ))}
      <div className="hl-axis">
        <span className="hl-species" />
        <div className="hl-ticks">
          {TICKS.map((t) => (
            <span key={t.label} style={{ left: `${position(t.hours)}%` }}>
              {t.label}
            </span>
          ))}
        </div>
      </div>
    </figure>
  )
}
