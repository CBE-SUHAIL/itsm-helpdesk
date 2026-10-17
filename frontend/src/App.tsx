import { useEffect, useState } from 'react'
import { AuthProvider } from './auth'
import { useAuth } from './authContext'
import { LoginPage } from './LoginPage'
import { UserManagement } from './UserManagement'
import { TicketList, TicketDetail, CreateTicket } from './Tickets'
import { Notifications } from './Notifications'
import { KnowledgeBase } from './KnowledgeBase'
import { DashboardReports } from './DashboardReports'
import { AdminCategories, AdminSettings, AuditLogs } from './AdminTools'
import './App.css'
import './features.css'

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

  const links = [
    { path: '/', label: 'Dashboard' },
    { path: '/tickets', label: user.role === 'Employee' ? 'My tickets' : 'Support queue' },
    { path: '/articles', label: 'Knowledge base' },
    { path: '/notifications', label: 'Notifications' },
  ]
  if (user.role !== 'Employee') links.push({ path: '/reports', label: 'Reports' })
  if (user.role === 'Admin') links.push(
    { path: '/admin/users', label: 'Users' },
    { path: '/admin/categories', label: 'Categories' },
    { path: '/admin/settings', label: 'Settings' },
    { path: '/admin/audit', label: 'Audit log' },
  )
  const ticketId = path.startsWith('/tickets/') && path !== '/tickets/new' ? path.slice('/tickets/'.length) : null
  const allowed = links.some((link) => link.path === path) || Boolean(ticketId) ||
    (path === '/tickets/new' && user.role === 'Employee')

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
        {links.map((link) => <a key={link.path} href={link.path} className={path === link.path || (link.path === '/tickets' && path.startsWith('/tickets/')) ? 'selected' : ''}
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
        {allowed && path === '/admin/categories' && <AdminCategories />}
        {allowed && path === '/admin/settings' && <AdminSettings />}
        {allowed && path === '/admin/audit' && <AuditLogs />}
        {allowed && path === '/' && <DashboardReports />}
        {allowed && path === '/reports' && <DashboardReports />}
        {allowed && path === '/articles' && <KnowledgeBase />}
        {allowed && path === '/notifications' && <Notifications onTicket={(id) => navigate(`/tickets/${id}`)} />}
        {allowed && path === '/tickets' && <TicketList onOpen={(id) => navigate(`/tickets/${id}`)} onCreate={() => navigate('/tickets/new')} />}
        {allowed && path === '/tickets/new' && <CreateTicket onCreated={(id) => navigate(`/tickets/${id}`)} onCancel={() => navigate('/tickets')} />}
        {allowed && ticketId && <TicketDetail id={ticketId} onBack={() => navigate('/tickets')} />}
      </main>
    </div>
  </div>
}

function App() {
  return <AuthProvider><Workspace /></AuthProvider>
}

export default App
