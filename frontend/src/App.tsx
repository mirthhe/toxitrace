import { useEffect, useState } from 'react'
import { analyze, getHealth, setAccessCode } from './api'
import { ContextTab } from './components/ContextTab'
import { EvidenceTab } from './components/EvidenceTab'
import { OverviewTab } from './components/OverviewTab'
import { PredictionsTab } from './components/PredictionsTab'
import { SummaryHeader } from './components/SummaryHeader'
import { SupportTab } from './components/SupportTab'
import { TraceTab } from './components/TraceTab'
import { downloadJson } from './export'
import { TraceNavigation, type TabId } from './navigation'
import type { AnalysisResult, Health } from './types'

const DEMO_LABELS: Record<string, string> = {
  '62-75-9': 'NDMA',
  '335-67-1': 'PFOA',
  'O=NN1CC2CC(C1)c1cc3nccnc3cc12': 'N-nitroso-varenicline',
}

const TABS: { id: TabId; label: string }[] = [
  { id: 'overview', label: 'Overview' },
  { id: 'predictions', label: 'Predictions' },
  { id: 'evidence', label: 'Evidence' },
  { id: 'support', label: 'Structural support' },
  { id: 'context', label: 'Context' },
  { id: 'trace', label: 'Trace' },
]

type State =
  | { kind: 'idle' }
  | { kind: 'running'; input: string }
  | { kind: 'error'; message: string }
  | { kind: 'done'; result: AnalysisResult }

export default function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [input, setInput] = useState('')
  const [state, setState] = useState<State>({ kind: 'idle' })

  const refreshHealth = () =>
    getHealth()
      .then(setHealth)
      .catch(() => setHealth(null))

  useEffect(() => {
    refreshHealth()
  }, [])

  function changeAccessCode(code: string | null) {
    setAccessCode(code)
    refreshHealth()
  }

  async function run(text: string) {
    const trimmed = text.trim()
    if (!trimmed) {
      setState({
        kind: 'error',
        message: 'Enter a chemical name, CAS number, DTXSID or SMILES.',
      })
      return
    }
    setInput(trimmed)
    setState({ kind: 'running', input: trimmed })
    try {
      setState({ kind: 'done', result: await analyze(trimmed) })
    } catch (err) {
      setState({
        kind: 'error',
        message: err instanceof Error ? err.message : String(err),
      })
    }
  }

  return (
    <div className="page">
      <div className="hero">
        <header className="masthead">
          <div className="brand">
            <Logo />
            <span className="wordmark">ToxiTrace</span>
          </div>
          <ModeBadge health={health} onAccessCode={changeAccessCode} />
        </header>

        <section className="intro">
          <p className="eyebrow">Ames mutagenicity · weight of evidence</p>
          <h1>How far can a mutagenicity prediction be trusted?</h1>
          <p className="lede">
            ToxiTrace checks a ToxIndex prediction against independent sources and shows every call it is based on.
          </p>
        </section>

        <form
          className="query"
          onSubmit={(e) => {
            e.preventDefault()
            run(input)
          }}
        >
          <div className="query-row">
            <input
              aria-label="Chemical"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Chemical name, CAS number, DTXSID or SMILES"
              autoComplete="off"
              spellCheck={false}
            />
            <button type="submit" className="primary" disabled={state.kind === 'running'}>
              {state.kind === 'running' ? 'Analysing…' : 'Analyse →'}
            </button>
          </div>
          {health && (
            <div className="demos">
              <span>Try</span>
              {health.demo_inputs.map((demo) => (
                <button type="button" key={demo} className="chip" onClick={() => run(demo)}>
                  {DEMO_LABELS[demo] ?? demo}
                </button>
              ))}
            </div>
          )}
        </form>
      </div>

      {state.kind === 'error' && <div className="alert">{state.message}</div>}
      {state.kind === 'running' && <p className="muted">Analysing {state.input}…</p>}
      {state.kind === 'done' && <Result key={state.result.chemical_input} result={state.result} health={health} />}
    </div>
  )
}

function Logo() {
  // A hexagon (ring) with a trace line through it.
  return (
    <svg className="logo" viewBox="0 0 32 32" aria-hidden="true">
      <path d="M16 3 27 9.5v13L16 29 5 22.5v-13Z" fill="none" stroke="currentColor" strokeWidth="2" />
      <path
        d="M3 18h7l3-6 4 10 3-4h9"
        fill="none"
        stroke="var(--accent-warm)"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function ModeBadge({ health, onAccessCode }: { health: Health | null; onAccessCode: (code: string | null) => void }) {
  const [editing, setEditing] = useState(false)
  const [code, setCode] = useState('')

  if (!health) return <span className="mode mode-down">Backend unreachable</span>

  if (health.mode === 'live') {
    return (
      <div className="mode-group">
        <span className="mode mode-live" title="Each analysis calls ToxIndex, PubChem and Claude.">
          Live APIs{health.toxindex_key_configured ? '' : ' · no ToxIndex key'}
        </span>
        {health.access_code_required && (
          <button type="button" className="mode-action" onClick={() => onAccessCode(null)}>
            Back to demo
          </button>
        )}
      </div>
    )
  }

  return (
    <div className="mode-group">
      <span className="mode mode-offline" title="Answers come from recorded real API responses, not live calls.">
        Offline · recorded responses
      </span>
      {health.access_code_required &&
        (editing ? (
          <form
            className="unlock"
            onSubmit={(e) => {
              e.preventDefault()
              onAccessCode(code.trim() || null)
              setEditing(false)
            }}
          >
            <input
              aria-label="Access code"
              type="password"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="Access code"
              autoFocus
            />
            <button type="submit" className="mode-action">
              Unlock
            </button>
          </form>
        ) : (
          <button type="button" className="mode-action" onClick={() => setEditing(true)}>
            {health.access_code_rejected ? 'Code not accepted · try again' : 'Unlock live mode'}
          </button>
        ))}
    </div>
  )
}

function Result({ result, health }: { result: AnalysisResult; health: Health | null }) {
  const [tab, setTab] = useState<TabId>('overview')
  const [highlight, setHighlight] = useState<string | null>(null)

  function goToRef(ref: string) {
    setHighlight(ref)
    setTab('trace')
  }

  return (
    <TraceNavigation.Provider value={goToRef}>
      <main className="result">
        <SummaryHeader result={result} />

        <div className="tabbed">
          <div className="tabs-bar">
            <nav className="tabs" role="tablist">
              {TABS.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  role="tab"
                  aria-selected={tab === t.id}
                  className={`tab${tab === t.id ? ' active' : ''}`}
                  onClick={() => setTab(t.id)}
                >
                  {t.label}
                  {t.id === 'trace' && <span className="tab-count">{result.trace.length}</span>}
                </button>
              ))}
            </nav>
            <button type="button" className="secondary" onClick={() => downloadJson(result, health)}>
              Export JSON
            </button>
          </div>

          <div className="card tab-panel" role="tabpanel">
            {tab === 'overview' && <OverviewTab result={result} />}
            {tab === 'predictions' && <PredictionsTab result={result} />}
            {tab === 'evidence' && <EvidenceTab result={result} />}
            {tab === 'support' && <SupportTab result={result} />}
            {tab === 'context' && <ContextTab result={result} />}
            {tab === 'trace' && <TraceTab entries={result.trace} highlight={highlight} />}
          </div>
        </div>
      </main>
    </TraceNavigation.Provider>
  )
}
