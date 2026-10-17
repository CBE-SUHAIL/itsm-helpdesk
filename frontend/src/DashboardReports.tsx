import { useEffect, useState } from 'react'
import { apiMessage } from './api'
import type { Category, Dashboard, Page, Priority, TicketStatus } from './api'
import { useAuth } from './authContext'

const statuses: TicketStatus[] = ['Open', 'Assigned', 'In Progress', 'Resolved', 'Closed']
const priorities: Priority[] = ['Low', 'Medium', 'High', 'Critical']

export function DashboardReports() {
  const { request, user } = useAuth()
  const [summary, setSummary] = useState<Dashboard | null>(null)
  const [categories, setCategories] = useState<Category[]>([])
  const [status, setStatus] = useState('')
  const [priority, setPriority] = useState('')
  const [category, setCategory] = useState('')
  const [assignee, setAssignee] = useState('')
  const [createdFrom, setCreatedFrom] = useState('')
  const [createdTo, setCreatedTo] = useState('')
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    const load = () => void request<Dashboard>('/dashboard/summary').then((value) => { if (active) { setSummary(value); setError('') } }).catch((cause) => { if (active) setError(apiMessage(cause)) })
    load(); const timer = window.setInterval(load, 15000)
    return () => { active = false; window.clearInterval(timer) }
  }, [request])
  useEffect(() => { void request<Page<Category>>('/categories?limit=100').then((value) => setCategories(value.items)).catch(() => {}) }, [request])
  async function download(format: 'csv' | 'pdf') {
    const query = new URLSearchParams({ format })
    if (status) query.set('status', status)
    if (priority) query.set('priority', priority)
    if (category) query.set('category_id', category)
    if (assignee.trim()) query.set('assignee_id', assignee.trim())
    if (createdFrom) query.set('created_from', `${createdFrom}T00:00:00Z`)
    if (createdTo) query.set('created_to', `${createdTo}T23:59:59Z`)
    try {
      const blob = await request<Blob>(`/reports/tickets?${query}`)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a'); link.href = url; link.download = `itsm-tickets.${format}`; link.click()
      window.setTimeout(() => URL.revokeObjectURL(url), 1000)
      setError('')
    } catch (cause) { setError(apiMessage(cause)) }
  }
  const maxStatus = Math.max(1, ...Object.values(summary?.counts_by_status ?? {}))
  return <div className="content-width"><div className="page-heading"><div><span className="eyebrow">OVERVIEW</span><h1>Dashboard & reports</h1><p>{user?.role === 'Employee' ? 'Your ticket activity.' : 'Support activity across the helpdesk.'}</p></div></div>
    {error && <p className="form-error" role="alert">{error}</p>}
    {!summary ? <p className="empty">Loading dashboard…</p> : <>
      <div className="metric-grid"><div className="panel"><small>Total tickets</small><strong>{Object.values(summary.counts_by_status).reduce((a, b) => a + b, 0)}</strong></div><div className="panel"><small>Response overdue</small><strong>{summary.response_overdue_count}</strong></div><div className="panel"><small>Resolution overdue</small><strong>{summary.resolution_overdue_count}</strong></div><div className="panel"><small>In progress</small><strong>{summary.counts_by_status['In Progress'] ?? 0}</strong></div></div>
      <div className="two-column"><section className="panel"><h2>By status</h2>{statuses.map((item) => <div className="bar-row" key={item}><span>{item}</span><div className="bar-track"><div style={{ width: `${100 * (summary.counts_by_status[item] ?? 0) / maxStatus}%` }} /></div><strong>{summary.counts_by_status[item] ?? 0}</strong></div>)}</section><section className="panel"><h2>By priority</h2>{priorities.map((item) => <div className="bar-row" key={item}><span>{item}</span><div className="bar-track"><div style={{ width: `${100 * (summary.counts_by_priority[item] ?? 0) / Math.max(1, ...Object.values(summary.counts_by_priority))}%` }} /></div><strong>{summary.counts_by_priority[item] ?? 0}</strong></div>)}</section></div>
      {summary.agent_workload && <section className="panel"><h2>Agent workload</h2><p className="muted">Assigned or in-progress tickets by agent.</p>{Object.entries(summary.agent_workload).length ? Object.entries(summary.agent_workload).map(([id, count]) => <p key={id}>{id.slice(0, 8)}: {count} ticket{count === 1 ? '' : 's'}</p>) : <p className="muted">No active assignments.</p>}</section>}
    </>}
    {user?.role !== 'Employee' && <section className="panel report-panel"><h2>Export ticket report</h2><p className="muted">Download filtered records as CSV or PDF.</p><div className="filter-bar"><label>Status<select value={status} onChange={(event) => setStatus(event.target.value)}><option value="">All</option>{statuses.map((item) => <option key={item}>{item}</option>)}</select></label><label>Priority<select value={priority} onChange={(event) => setPriority(event.target.value)}><option value="">All</option>{priorities.map((item) => <option key={item}>{item}</option>)}</select></label><label>Category<select value={category} onChange={(event) => setCategory(event.target.value)}><option value="">All</option>{categories.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}</select></label><label>Assignee ID<input value={assignee} onChange={(event) => setAssignee(event.target.value)} placeholder="Optional agent UUID" /></label><label>From<input type="date" value={createdFrom} onChange={(event) => setCreatedFrom(event.target.value)} /></label><label>To<input type="date" value={createdTo} onChange={(event) => setCreatedTo(event.target.value)} /></label></div><div className="row-actions"><button onClick={() => void download('csv')}>Download CSV</button><button className="secondary" onClick={() => void download('pdf')}>Download PDF</button></div></section>}
  </div>
}
