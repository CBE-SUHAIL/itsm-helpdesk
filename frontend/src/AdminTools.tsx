import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { apiMessage } from './api'
import type { AuditLog, Category, Page, Priority, Settings } from './api'
import { useAuth } from './authContext'

const priorities: Priority[] = ['Low', 'Medium', 'High', 'Critical']

export function AdminSettings() {
  const { request } = useAuth()
  const [settings, setSettings] = useState<Settings | null>(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  useEffect(() => { void request<Settings>('/settings').then(setSettings).catch((cause) => setError(apiMessage(cause))) }, [request])
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!settings) return
    const data = new FormData(event.currentTarget)
    const sla_targets = Object.fromEntries(priorities.map((priority) => [priority, {
      first_response_hours: Number(data.get(`${priority}_response`)),
      resolution_hours: Number(data.get(`${priority}_resolution`)),
    }]))
    const allowed_attachment_types = ['application/pdf', 'image/png', 'image/jpeg', 'text/plain'].filter((type) => data.get(type) === 'on')
    try {
      const result = await request<Settings>('/settings', { method: 'PATCH', body: JSON.stringify({ sla_targets, max_attachment_bytes: Number(data.get('max_attachment_bytes')), allowed_attachment_types }) })
      setSettings(result); setNotice('Settings saved.'); setError('')
    } catch (cause) { setError(apiMessage(cause)) }
  }
  return <div className="content-width"><div className="page-heading"><div><span className="eyebrow">ADMINISTRATION</span><h1>Settings</h1><p>New tickets and uploads use these limits. Existing ticket deadlines remain unchanged.</p></div></div>
    {error && <p className="form-error" role="alert">{error}</p>}{notice && <p className="form-success" role="status">{notice}</p>}
    {settings ? <form className="stack-form" onSubmit={(event) => void save(event)}><section className="panel"><h2>SLA targets (calendar hours)</h2><div className="settings-grid"><strong>Priority</strong><strong>First response</strong><strong>Resolution</strong>{priorities.map((priority) => <div className="contents" key={priority}><span>{priority}</span><input name={`${priority}_response`} type="number" min={1} required defaultValue={settings.sla_targets[priority].first_response_hours} /><input name={`${priority}_resolution`} type="number" min={1} required defaultValue={settings.sla_targets[priority].resolution_hours} /></div>)}</div></section><section className="panel"><h2>Attachments</h2><label>Maximum bytes<input name="max_attachment_bytes" type="number" min={1} required defaultValue={settings.max_attachment_bytes} /></label><div className="checkbox-row">{['application/pdf', 'image/png', 'image/jpeg', 'text/plain'].map((type) => <label key={type}><input name={type} type="checkbox" defaultChecked={settings.allowed_attachment_types.includes(type)} /> {type}</label>)}</div></section><button>Save settings</button></form> : <p className="empty">Loading settings…</p>}
  </div>
}

export function AdminCategories() {
  const { request } = useAuth()
  const [categories, setCategories] = useState<Category[]>([])
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [editing, setEditing] = useState<Category | null>(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [revision, setRevision] = useState(0)
  useEffect(() => { void request<Page<Category>>('/categories?limit=100&include_inactive=true').then((value) => setCategories(value.items)).catch((cause) => setError(apiMessage(cause))) }, [request, revision])
  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    try { await request('/categories', { method: 'POST', body: JSON.stringify({ name, description }) }); setName(''); setDescription(''); setNotice('Category created.'); setRevision((value) => value + 1); setError('') }
    catch (cause) { setError(apiMessage(cause)) }
  }
  async function toggle(category: Category) {
    if (category.is_active && !window.confirm(`Deactivate ${category.name}? Existing tickets will keep it.`)) return
    try { await request(`/categories/${category.id}`, { method: 'PATCH', body: JSON.stringify({ is_active: !category.is_active }) }); setNotice(category.is_active ? 'Category deactivated.' : 'Category reactivated.'); setRevision((value) => value + 1); setError('') }
    catch (cause) { setError(apiMessage(cause)) }
  }
  async function update(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!editing) return
    const data = new FormData(event.currentTarget)
    try { await request(`/categories/${editing.id}`, { method: 'PATCH', body: JSON.stringify({ name: data.get('name'), description: data.get('description') }) }); setEditing(null); setNotice('Category updated.'); setRevision((value) => value + 1); setError('') }
    catch (cause) { setError(apiMessage(cause)) }
  }
  return <div className="content-width"><div className="page-heading"><div><span className="eyebrow">ADMINISTRATION</span><h1>Categories</h1><p>Organise ticket and article topics.</p></div></div>{error && <p className="form-error" role="alert">{error}</p>}{notice && <p className="form-success" role="status">{notice}</p>}
    <div className="two-column"><section className="panel"><h2>Categories</h2>{categories.map((item) => <div className="feed-item" key={item.id}><strong>{item.name}</strong> <span className={`pill ${item.is_active ? 'active' : 'inactive'}`}>{item.is_active ? 'Active' : 'Inactive'}</span><p>{item.description}</p><div className="row-actions"><button className="text-button" onClick={() => setEditing(item)}>Edit</button><button className="text-button" onClick={() => void toggle(item)}>{item.is_active ? 'Deactivate' : 'Reactivate'}</button></div></div>)}{categories.length === 0 && <p className="muted">No categories.</p>}</section><section className="panel"><h2>New category</h2><form className="stack-form compact" onSubmit={(event) => void create(event)}><label>Name<input value={name} onChange={(event) => setName(event.target.value)} maxLength={80} required /></label><label>Description<textarea value={description} onChange={(event) => setDescription(event.target.value)} maxLength={500} rows={3} /></label><button>Add category</button></form></section></div>
    {editing && <div className="dialog-backdrop" role="presentation" onMouseDown={() => setEditing(null)}><section className="dialog" role="dialog" aria-modal="true" aria-labelledby="category-heading" onMouseDown={(event) => event.stopPropagation()}><div className="dialog-head"><h2 id="category-heading">Edit category</h2><button className="text-button" onClick={() => setEditing(null)}>Close</button></div><form onSubmit={(event) => void update(event)}><label>Name<input name="name" required maxLength={80} defaultValue={editing.name} /></label><label>Description<textarea name="description" maxLength={500} rows={3} defaultValue={editing.description} /></label>{error && <p className="form-error" role="alert">{error}</p>}<button>Save</button></form></section></div>}
  </div>
}

export function AuditLogs() {
  const { request } = useAuth()
  const [page, setPage] = useState<Page<AuditLog>>({ items: [], total: 0 })
  const [offset, setOffset] = useState(0)
  const [action, setAction] = useState('')
  const [entity, setEntity] = useState('')
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    const query = new URLSearchParams({ limit: '20', offset: String(offset) })
    if (action) query.set('action', action)
    if (entity) query.set('entity_type', entity)
    void request<Page<AuditLog>>(`/audit-logs?${query}`).then((value) => { if (active) setPage(value) }).catch((cause) => { if (active) setError(apiMessage(cause)) })
    return () => { active = false }
  }, [request, offset, action, entity])
  return <div className="content-width"><div className="page-heading"><div><span className="eyebrow">ADMINISTRATION</span><h1>Audit log</h1><p>Read-only history of important actions.</p></div></div><div className="filter-bar"><label>Action<input value={action} onChange={(event) => { setAction(event.target.value); setOffset(0) }} placeholder="e.g. ticket_update" /></label><label>Entity<input value={entity} onChange={(event) => { setEntity(event.target.value); setOffset(0) }} placeholder="e.g. ticket" /></label><span className="result-count">{page.total} entries</span></div>{error && <p className="form-error" role="alert">{error}</p>}<div className="table-wrap"><table><thead><tr><th>When</th><th>Action</th><th>Entity</th><th>Actor</th><th>Changes</th></tr></thead><tbody>{page.items.map((item) => <tr key={item.id}><td>{new Date(item.created_at).toLocaleString()}</td><td>{item.action}</td><td>{item.entity_type} {item.entity_id?.slice(0, 8)}</td><td>{item.actor_id?.slice(0, 8) ?? 'System'}</td><td><small>{JSON.stringify(item.new_value ?? {})}</small></td></tr>)}</tbody></table>{page.items.length === 0 && <p className="empty">No audit entries.</p>}</div><div className="pagination"><button className="secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 20))}>Previous</button><span>{page.total ? `${offset + 1}–${Math.min(offset + page.items.length, page.total)} of ${page.total}` : '0 entries'}</span><button className="secondary" disabled={offset + 20 >= page.total} onClick={() => setOffset(offset + 20)}>Next</button></div></div>
}
