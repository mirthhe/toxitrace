import { useEffect, useState } from 'react'
import { analyze, getHealth } from './api'
import { OverviewTab } from './components/OverviewTab'
import { SummaryHeader } from './components/SummaryHeader'
import { TraceTab } from './components/TraceTab'
import { downloadJson } from './export'
import { TraceNavigation, type TabId } from './navigation'
import type { AnalysisResult, Health } from './types'

const DEMO_LABELS: Record<string, string> = {
  '62-75-9': 'NDMA',
  '335-67-1': 'PFOA',
  'O=NN1CC2CC(C1)c1cc3nccnc3cc12': 'N-nitroso-varenicline',
}

// Tabs whose rules are not built yet show what they will contain (docs/plan.md §5).
const PLANNED: Partial<Record<TabId, { rules: string; text: string }>> = {
  predictions: {
    rules: 'R2–R4',
    text: 'AmesFormer, VEGA and structural alerts, each labelled as predicted, with disagreement and applicability-domain flags.',
  },
  evidence: {
    rules: 'R2, R7',
    text: 'An evidence matrix of measured and curated findings, with sources that returned nothing listed as "not retrieved".',
  },
  support: {
    rules: 'R5, R6',
    text: 'Nearest measured neighbours from MutagenLou2023 and whether the prediction is independent of them.',
  },
  context: {
    rules: 'R8, R9',
    text: 'EMA CPCA category and acceptable intake for N-nitroso compounds; httk toxicokinetic context.',
  },
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

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => setHealth(null))
  }, [])

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
          <ModeBadge health={health} />
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

function ModeBadge({ health }: { health: Health | null }) {
  if (!health) return <span className="mode mode-down">Backend unreachable</span>
  if (health.mode === 'offline') {
    return (
      <span className="mode mode-offline" title="Answers come from recorded real API responses, not live calls.">
        Offline · recorded responses
      </span>
    )
  }
  return (
    <span className="mode mode-live" title="Each analysis calls ToxIndex and PubChem.">
      Live APIs{health.toxindex_key_configured ? '' : ' · no ToxIndex key'}
    </span>
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
                  className={`tab${tab === t.id ? ' active' : ''}${PLANNED[t.id] ? ' planned' : ''}`}
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
            {tab === 'trace' && <TraceTab entries={result.trace} highlight={highlight} />}
            {PLANNED[tab] && <PlannedTab {...PLANNED[tab]} />}
          </div>
        </div>
      </main>
    </TraceNavigation.Provider>
  )
}

function PlannedTab({ rules, text }: { rules: string; text: string }) {
  return (
    <div className="tab-body planned-body">
      <p>
        <span className="rule">{rules}</span> Not built yet.
      </p>
      <p className="muted">{text}</p>
    </div>
  )
}
