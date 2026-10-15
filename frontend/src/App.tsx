import { useEffect, useState } from 'react'
import { AuthProvider } from './auth'
import { useAuth } from './authContext'
import { LoginPage } from './LoginPage'
import { UserManagement } from './UserManagement'
import './App.css'

function usePath() {
  const [path, setPath] = useState(window.location.pathname)
  useEffect(() => {
    const update = () => setPath(window.location.pathname)
    window.addEventListener('popstate', update)
    return () => window.removeEventListener('popstate', update)
  }, [])
  const navigate = (next: string) => {
    window.history.pushState({}, '', next)
    setPath(next)
  }
  return { path, navigate }
}

function Workspace() {
  const { user, loading, logout } = useAuth()
  const { path, navigate } = usePath()
  const [logoutError, setLogoutError] = useState('')

  if (loading) return <main className="loading-screen">Restoring your session…</main>
  if (!user) return <LoginPage />

  const links = [{ path: '/', label: 'Home' }]
  if (user.role === 'Admin') links.push({ path: '/admin/users', label: 'Users' })
  const allowed = links.some((link) => link.path === path)

  async function signOut() {
    setLogoutError('')
    try { await logout(); navigate('/') }
    catch { setLogoutError('Signed out locally, but the server could not confirm logout.') }
  }

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark">IT</span><span>ITSM<span className="brand-light"> Helpdesk</span></span></div>
      <p className="sidebar-label">WORKSPACE</p>
      <nav aria-label="Main navigation">
        {links.map((link) => <a key={link.path} href={link.path} className={path === link.path ? 'selected' : ''}
          onClick={(event) => { event.preventDefault(); navigate(link.path) }}>{link.label}</a>)}
      </nav>
      <div className="sidebar-bottom"><span className="avatar">{user.name.slice(0, 1).toUpperCase()}</span>
        <div><strong>{user.name}</strong><small>{user.role}</small></div></div>
    </aside>
    <div className="main-column">
      <header className="topbar"><span>Local service workspace</span><button className="text-button" onClick={() => void signOut()}>Sign out</button></header>
      {logoutError && <p className="form-error" role="alert">{logoutError}</p>}
      <main>
        {!allowed && <div className="content-width blocked"><span className="eyebrow">ACCESS RESTRICTED</span><h1>Page unavailable</h1><p>This page is not available to your account.</p><button onClick={() => navigate('/')}>Go home</button></div>}
        {allowed && path === '/admin/users' && <UserManagement />}
        {allowed && path === '/' && <div className="content-width home">
          <span className="eyebrow">{user.role.toUpperCase()} WORKSPACE</span>
          <h1>Welcome back, {user.name.split(' ')[0]}.</h1>
          <p>Your account is connected. Ticket screens arrive in the next project tasks; this phase completes sign-in, access controls, and admin user management.</p>
          <div className="home-card"><h2>{user.role === 'Admin' ? 'Manage your team' : 'Your workspace is ready'}</h2>
            <p>{user.role === 'Admin' ? 'Create accounts, assign roles, and deactivate users from the Users page.' : 'Your role determines which parts of the helpdesk you can access.'}</p>
            {user.role === 'Admin' && <button onClick={() => navigate('/admin/users')}>Open user management</button>}
          </div>
        </div>}
      </main>
    </div>
  </div>
}

function App() {
  return <AuthProvider><Workspace /></AuthProvider>
}

export default App
