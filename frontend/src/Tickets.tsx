import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { apiMessage } from './api'
import type { Attachment, Category, Comment, Page, Priority, Ticket, TicketHistory, TicketStatus, User } from './api'
import { useAuth } from './authContext'

const statuses: TicketStatus[] = ['Open', 'Assigned', 'In Progress', 'Resolved', 'Closed']
const priorities: Priority[] = ['Low', 'Medium', 'High', 'Critical']
const date = (value: string) => new Date(value).toLocaleString()

export function TicketList({ onOpen, onCreate }: { onOpen: (id: string) => void; onCreate: () => void }) {
  const { request, user } = useAuth()
  const [page, setPage] = useState<Page<Ticket>>({ items: [], total: 0 })
  const [categories, setCategories] = useState<Category[]>([])
  const [status, setStatus] = useState('')
  const [priority, setPriority] = useState('')
  const [category, setCategory] = useState('')
  const [search, setSearch] = useState('')
  const [offset, setOffset] = useState(0)
  const [error, setError] = useState('')

  useEffect(() => { void request<Page<Category>>('/categories?limit=100').then((value) => setCategories(value.items)).catch((cause) => setError(apiMessage(cause))) }, [request])
  useEffect(() => {
    let active = true
    const query = new URLSearchParams({ limit: '20', offset: String(offset) })
    if (status) query.set('status', status)
    if (priority) query.set('priority', priority)
    if (category) query.set('category_id', category)
    if (search.trim()) query.set('q', search.trim())
    const load = () => void request<Page<Ticket>>(`/tickets?${query}`).then((value) => { if (active) { setPage(value); setError('') } }).catch((cause) => { if (active) setError(apiMessage(cause)) })
    load()
    const interval = window.setInterval(load, 15000)
    return () => { active = false; window.clearInterval(interval) }
  }, [request, status, priority, category, search, offset])

  return <div className="content-width">
    <div className="page-heading"><div><span className="eyebrow">TICKETS</span><h1>{user?.role === 'Employee' ? 'My tickets' : 'Support queue'}</h1><p>Track requests through resolution.</p></div>
      {user?.role === 'Employee' && <button onClick={onCreate}>New ticket</button>}</div>
    <div className="filter-bar">
      <label>Search<input value={search} onChange={(event) => { setSearch(event.target.value); setOffset(0) }} placeholder="Title or description" /></label>
      <label>Status<select value={status} onChange={(event) => { setStatus(event.target.value); setOffset(0) }}><option value="">All</option>{statuses.map((item) => <option key={item}>{item}</option>)}</select></label>
      <label>Priority<select value={priority} onChange={(event) => { setPriority(event.target.value); setOffset(0) }}><option value="">All</option>{priorities.map((item) => <option key={item}>{item}</option>)}</select></label>
      <label>Category<select value={category} onChange={(event) => { setCategory(event.target.value); setOffset(0) }}><option value="">All</option>{categories.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      <span className="result-count">{page.total} tickets</span>
    </div>
    {error && <p className="form-error" role="alert">{error}</p>}
    <div className="table-wrap"><table><thead><tr><th>Ticket</th><th>Status</th><th>Priority</th><th>Category</th><th>Created</th><th>SLA</th></tr></thead>
      <tbody>{page.items.map((ticket) => <tr key={ticket.id} onClick={() => onOpen(ticket.id)} className="clickable-row">
        <td><strong>{ticket.title}</strong><small className="cell-subtitle">{ticket.id.slice(0, 8)}</small></td>
        <td><span className="pill active">{ticket.status}</span></td><td>{ticket.priority}</td>
        <td>{categories.find((item) => item.id === ticket.category_id)?.name ?? ticket.category_id.slice(0, 8)}</td>
        <td>{date(ticket.created_at)}</td><td>{ticket.response_overdue || ticket.resolution_overdue ? <span className="pill danger">Overdue</span> : 'On time'}</td>
      </tr>)}</tbody></table>{page.items.length === 0 && <p className="empty">No tickets match these filters.</p>}</div>
    <div className="pagination"><button className="secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 20))}>Previous</button><span>{page.total ? `${offset + 1}–${Math.min(offset + page.items.length, page.total)} of ${page.total}` : '0 tickets'}</span><button className="secondary" disabled={offset + 20 >= page.total} onClick={() => setOffset(offset + 20)}>Next</button></div>
  </div>
}

export function CreateTicket({ onCreated, onCancel }: { onCreated: (id: string) => void; onCancel: () => void }) {
  const { request } = useAuth()
  const [categories, setCategories] = useState<Category[]>([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => { void request<Page<Category>>('/categories?limit=100').then((value) => setCategories(value.items)).catch((cause) => setError(apiMessage(cause))) }, [request])
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    setBusy(true); setError('')
    try {
      const ticket = await request<Ticket>('/tickets', { method: 'POST', body: JSON.stringify({ title: data.get('title'), description: data.get('description'), category_id: data.get('category_id') }) })
      onCreated(ticket.id)
    } catch (cause) { setError(apiMessage(cause)) } finally { setBusy(false) }
  }
  return <div className="content-width narrow"><button className="text-button" onClick={onCancel}>← Tickets</button><span className="eyebrow">NEW REQUEST</span><h1>Create a ticket</h1>
    <form className="stack-form" onSubmit={(event) => void submit(event)}>
      <label>Title<input name="title" required maxLength={200} /></label>
      <label>Category<select name="category_id" required defaultValue=""><option value="" disabled>Choose a category</option>{categories.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      <label>Description<textarea name="description" required rows={7} /></label>
      <p className="muted">New tickets start Open and Medium priority.</p>
      {error && <p className="form-error" role="alert">{error}</p>}
      <button disabled={busy || categories.length === 0}>Submit ticket</button>
    </form></div>
}

export function TicketDetail({ id, onBack }: { id: string; onBack: () => void }) {
  const { request, user } = useAuth()
  const [ticket, setTicket] = useState<Ticket | null>(null)
  const [comments, setComments] = useState<Comment[]>([])
  const [history, setHistory] = useState<TicketHistory[]>([])
  const [attachments, setAttachments] = useState<Attachment[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [agents, setAgents] = useState<User[]>([])
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [refresh, setRefresh] = useState(0)

  useEffect(() => {
    let active = true
    const load = async () => {
      try {
        const [item, notes, changes, files] = await Promise.all([
          request<Ticket>(`/tickets/${id}`), request<Page<Comment>>(`/tickets/${id}/comments?limit=100`),
          request<Page<TicketHistory>>(`/tickets/${id}/history?limit=100`),
          request<Page<Attachment>>(`/tickets/${id}/attachments?limit=100`),
        ])
        if (active) { setTicket(item); setComments(notes.items); setHistory(changes.items); setAttachments(files.items); setError('') }
      } catch (cause) { if (active) setError(apiMessage(cause)) }
    }
    void load()
    const interval = window.setInterval(() => void load(), 15000)
    return () => { active = false; window.clearInterval(interval) }
  }, [request, id, refresh])
  useEffect(() => { void request<Page<Category>>('/categories?limit=100').then((value) => setCategories(value.items)).catch(() => {}) }, [request])
  useEffect(() => { if (user?.role === 'Admin') void request<Page<User>>('/users?role=Support+agent&limit=100').then((value) => setAgents(value.items.filter((item) => item.is_active))).catch(() => {}) }, [request, user?.role])

  async function action(path: string, body: Record<string, unknown>, message: string): Promise<boolean> {
    setError(''); setNotice('')
    try { await request(`/tickets/${id}/${path}`, { method: 'POST', body: JSON.stringify(body) }); setNotice(message); setRefresh((value) => value + 1); return true }
    catch (cause) { setError(apiMessage(cause)); return false }
  }
  async function addComment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget; const data = new FormData(form)
    if (await action('comments', { body: data.get('body') }, 'Comment added.')) form.reset()
  }
  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget; const data = new FormData(form)
    setError('')
    try { await request(`/tickets/${id}/attachments`, { method: 'POST', body: data }); setNotice('File uploaded.'); form.reset(); setRefresh((value) => value + 1) }
    catch (cause) { setError(apiMessage(cause)) }
  }
  async function download(file: Attachment) {
    try {
      const blob = await request<Blob>(`/tickets/${id}/attachments/${file.id}`)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a'); link.href = url; link.download = file.file_name; link.click()
      window.setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (cause) { setError(apiMessage(cause)) }
  }

  const canComment = ticket && (user?.role === 'Admin' || ticket.creator_id === user?.id || ticket.assignee_id === user?.id)
  const canWork = ticket && ticket.assignee_id === user?.id && (user?.role === 'Support agent' || user?.role === 'Admin')
  const canManage = ticket && (user?.role === 'Admin' || canWork)
  const canClose = ticket?.status === 'Resolved' && (user?.role === 'Admin' || ticket.creator_id === user?.id)
  return <div className="content-width"><button className="text-button" onClick={onBack}>← Tickets</button>
    {error && <p className="form-error" role="alert">{error}</p>}{notice && <p className="form-success" role="status">{notice}</p>}
    {!ticket ? <p className="empty">Loading ticket…</p> : <>
      <div className="page-heading"><div><span className="eyebrow">TICKET {ticket.id.slice(0, 8)}</span><h1>{ticket.title}</h1><p>{ticket.description}</p></div><span className="pill active">{ticket.status}</span></div>
      <div className="metric-grid"><div className="panel"><small>Priority</small><strong>{ticket.priority}</strong></div><div className="panel"><small>Response due</small><strong>{date(ticket.response_due_at)}</strong></div><div className="panel"><small>Resolution due</small><strong>{date(ticket.resolution_due_at)}</strong></div><div className="panel"><small>SLA</small><strong>{ticket.response_overdue || ticket.resolution_overdue ? 'Overdue' : 'On time'}</strong></div></div>
      <div className="two-column"><section className="panel"><h2>Manage ticket</h2>
        <p className="muted">Category: {categories.find((item) => item.id === ticket.category_id)?.name ?? ticket.category_id}</p>
        {user?.role === 'Support agent' && ticket.status === 'Open' && !ticket.assignee_id && <button onClick={() => void action('assignment', { assignee_id: user.id }, 'Ticket assigned to you.')}>Assign to me</button>}
        {user?.role === 'Admin' && ['Open', 'Assigned', 'In Progress'].includes(ticket.status) && <form className="inline-form" onSubmit={(event) => { event.preventDefault(); const data = new FormData(event.currentTarget); void action('assignment', { assignee_id: data.get('assignee_id') || null }, 'Assignment updated.') }}><label>Assign agent<select name="assignee_id" defaultValue={ticket.assignee_id ?? ''}><option value="">Unassigned</option>{agents.map((agent) => <option key={agent.id} value={agent.id}>{agent.name}</option>)}</select></label><button>Save</button></form>}
        {canWork && ticket.status === 'Assigned' && <button onClick={() => void action('status', { status: 'In Progress' }, 'Work started.')}>Start work</button>}
        {canWork && ticket.status === 'In Progress' && <form className="stack-form compact" onSubmit={(event) => { event.preventDefault(); const data = new FormData(event.currentTarget); void action('status', { status: 'Resolved', resolution_note: data.get('resolution_note') }, 'Ticket resolved.') }}><label>Resolution note<textarea name="resolution_note" required rows={3} /></label><button>Resolve</button></form>}
        {canWork && ticket.status === 'Resolved' && <button onClick={() => void action('status', { status: 'In Progress' }, 'Ticket returned to work.')}>Resume work</button>}
        {canClose && <button onClick={() => void action('status', { status: 'Closed' }, 'Ticket closed.')}>Close ticket</button>}
        {canManage && <form className="inline-form" onSubmit={(event) => { event.preventDefault(); const data = new FormData(event.currentTarget); void action('priority', { priority: data.get('priority'), reason: data.get('reason') }, 'Priority updated.') }}><label>Priority<select name="priority" defaultValue={ticket.priority}>{priorities.map((item) => <option key={item}>{item}</option>)}</select></label><label>Reason<input name="reason" required /></label><button>Change</button></form>}
        {canManage && <form className="inline-form" onSubmit={(event) => { event.preventDefault(); const data = new FormData(event.currentTarget); void action('category', { category_id: data.get('category_id'), reason: data.get('reason') }, 'Category updated.') }}><label>Category<select name="category_id" defaultValue={ticket.category_id}>{categories.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Reason<input name="reason" required /></label><button>Change</button></form>}
      </section><section className="panel"><h2>Conversation</h2>{comments.map((comment) => <div className="feed-item" key={comment.id}><p>{comment.body}</p><small>{date(comment.created_at)}</small></div>)}{comments.length === 0 && <p className="muted">No comments yet.</p>}{canComment && <form className="stack-form compact" onSubmit={(event) => void addComment(event)}><label>Add comment<textarea name="body" required rows={3} /></label><button>Post comment</button></form>}</section></div>
      <div className="two-column"><section className="panel"><h2>Attachments</h2>{attachments.map((file) => <div className="feed-item" key={file.id}><button className="text-button" onClick={() => void download(file)}>{file.file_name}</button><small>{Math.ceil(file.size_bytes / 1024)} KB</small></div>)}{attachments.length === 0 && <p className="muted">No files attached.</p>}{canComment && <form className="inline-form" onSubmit={(event) => void upload(event)}><label>Upload PDF, PNG, JPEG or TXT<input name="file" type="file" accept=".pdf,.png,.jpg,.jpeg,.txt" required /></label><button>Upload</button></form>}</section>
        <section className="panel"><h2>History</h2>{history.map((entry) => <div className="feed-item" key={entry.id}><strong>{entry.field}</strong><p>{entry.old_value ?? '—'} → {entry.new_value ?? '—'}</p>{entry.reason && <p>{entry.reason}</p>}<small>{date(entry.created_at)}</small></div>)}{history.length === 0 && <p className="muted">No changes yet.</p>}</section></div>
    </>}
  </div>
}
