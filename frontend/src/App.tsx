import { useEffect, useState } from 'react'
import './App.css'

type Health = {
  status: string
  database: string
}

type State =
  | { kind: 'loading' }
  | { kind: 'loaded'; health: Health }
  | { kind: 'error'; message: string }

// F03/F04 placeholder page. Its only job is to prove the React app can reach
// the FastAPI backend and that the backend can reach PostgreSQL. Real screens
// arrive with the checklist rows that specify them (A04, T08, T09, ...).
function App() {
  const [state, setState] = useState<State>({ kind: 'loading' })

  useEffect(() => {
    const controller = new AbortController()

    async function load() {
      try {
        const response = await fetch('/api/v1/health', { signal: controller.signal })
        const health = (await response.json()) as Health
        setState({ kind: 'loaded', health })
      } catch (error) {
        if (controller.signal.aborted) return
        setState({
          kind: 'error',
          message: error instanceof Error ? error.message : String(error),
        })
      }
    }

    void load()
    return () => controller.abort()
  }, [])

  return (
    <main className="status-page">
      <h1>ITSM helpdesk</h1>
      <p className="subtitle">
        F03/F04 scaffold. This page proves the React app can reach the API and
        that the API can reach PostgreSQL.
      </p>

      {state.kind === 'loading' && <p className="line">Checking the backend...</p>}

      {state.kind === 'loaded' && (
        <ul className="checks">
          <li className={state.health.status === 'ok' ? 'pass' : 'fail'}>
            backend: {state.health.status}
          </li>
          <li className={state.health.database === 'ok' ? 'pass' : 'fail'}>
            database: {state.health.database}
          </li>
        </ul>
      )}

      {state.kind === 'error' && (
        <div className="failure">
          <p className="line fail">Could not reach the backend.</p>
          <p className="hint">
            Start it from <code>backend/</code> with{' '}
            <code>uvicorn app.main:app --reload</code>.
          </p>
          <p className="hint">{state.message}</p>
        </div>
      )}
    </main>
  )
}

export default App
