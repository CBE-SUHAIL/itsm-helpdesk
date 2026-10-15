import { useState } from 'react'
import type { FormEvent } from 'react'
import { apiMessage } from './api'
import { useAuth } from './authContext'

export function LoginPage() {
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setBusy(true)
    try { await login(email, password) }
    catch (cause) { setError(apiMessage(cause)) }
    finally { setBusy(false) }
  }

  return <main className="login-layout">
    <section className="login-intro">
      <span className="eyebrow">ITSM / LOCAL WORKSPACE</span>
      <h1>Support starts here.</h1>
      <p>One place for employees, support agents, and admins to manage IT requests.</p>
      <div className="intro-note">Demo accounts are created locally. Use the password chosen during setup on this computer.</div>
    </section>
    <section className="login-card" aria-labelledby="login-heading">
      <span className="eyebrow">WELCOME BACK</span>
      <h2 id="login-heading">Sign in</h2>
      <p className="muted">Use your helpdesk account to continue.</p>
      <form onSubmit={(event) => void submit(event)}>
        <label htmlFor="email">Email address</label>
        <input id="email" type="email" autoComplete="username" required value={email} onChange={(event) => setEmail(event.target.value)} />
        <label htmlFor="password">Password</label>
        <input id="password" type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} />
        {error && <p className="form-error" role="alert">{error}</p>}
        <button type="submit" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
      </form>
      <p className="login-footnote">This is a local internship demo. No public registration.</p>
    </section>
  </main>
}
