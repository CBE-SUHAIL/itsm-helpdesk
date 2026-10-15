import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { apiMessage } from './api'
import type { Role, User, UserPage } from './api'
import { useAuth } from './authContext'

const roles: Role[] = ['Employee', 'Support agent', 'Admin']

export function UserManagement() {
  const { request, user: self } = useAuth()
  const [page, setPage] = useState<UserPage>({ items: [], total: 0 })
  const [offset, setOffset] = useState(0)
  const [roleFilter, setRoleFilter] = useState('')
  const [activeFilter, setActiveFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [editing, setEditing] = useState<User | null>(null)
  const [reload, setReload] = useState(0)

  useEffect(() => {
    let current = true
    const query = new URLSearchParams({ limit: '20', offset: String(offset) })
    if (roleFilter) query.set('role', roleFilter)
    if (activeFilter) query.set('is_active', activeFilter)
    void request<UserPage>(`/users?${query}`)
      .then((result) => { if (current) setPage(result) })
      .catch((cause) => { if (current) setError(apiMessage(cause)) })
      .finally(() => { if (current) setLoading(false) })
    return () => { current = false }
  }, [request, offset, roleFilter, activeFilter, reload])

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    setError('')
    setNotice('')
    try {
      await request<User>('/users', {
        method: 'POST',
        body: JSON.stringify({
          name: form.get('name'), email: form.get('email'),
          password: form.get('password'), role: form.get('role'),
        }),
      })
      setShowCreate(false)
      setOffset(0)
      setNotice('User created.')
      setLoading(true)
      setReload((value) => value + 1)
    } catch (cause) { setError(apiMessage(cause)) }
  }

  async function update(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!editing) return
    const form = new FormData(event.currentTarget)
    setError('')
    setNotice('')
    try {
      await request<User>(`/users/${editing.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          name: form.get('name'), role: form.get('role'),
          is_active: form.get('is_active') === 'true',
        }),
      })
      setEditing(null)
      setNotice('User updated.')
      setLoading(true)
      setReload((value) => value + 1)
    } catch (cause) { setError(apiMessage(cause)) }
  }

  return <div className="content-width">
    <div className="page-heading">
      <div><span className="eyebrow">ADMINISTRATION</span><h1>Users</h1><p>Manage access without deleting ticket history.</p></div>
      <button onClick={() => { setEditing(null); setShowCreate(true); setError('') }}>Add user</button>
    </div>
    <div className="filter-bar">
      <label>Role<select value={roleFilter} onChange={(event) => { setLoading(true); setRoleFilter(event.target.value); setOffset(0) }}>
        <option value="">All roles</option>{roles.map((role) => <option key={role}>{role}</option>)}
      </select></label>
      <label>Status<select value={activeFilter} onChange={(event) => { setLoading(true); setActiveFilter(event.target.value); setOffset(0) }}>
        <option value="">All statuses</option><option value="true">Active</option><option value="false">Inactive</option>
      </select></label>
      <span className="result-count">{page.total} user{page.total === 1 ? '' : 's'}</span>
    </div>
    {error && <p className="form-error" role="alert">{error}</p>}
    {notice && <p className="form-success" role="status">{notice}</p>}
    <div className="table-wrap"><table>
      <thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Status</th><th>Action</th></tr></thead>
      <tbody>{page.items.map((member) => <tr key={member.id}>
        <td>{member.name}{member.id === self?.id && <span className="self-label">You</span>}</td>
        <td>{member.email}</td><td>{member.role}</td>
        <td><span className={`pill ${member.is_active ? 'active' : 'inactive'}`}>{member.is_active ? 'Active' : 'Inactive'}</span></td>
        <td><button className="text-button" onClick={() => { setShowCreate(false); setEditing(member); setError('') }}>Edit</button></td>
      </tr>)}</tbody>
    </table>
      {loading && <p className="empty">Loading users…</p>}
      {!loading && page.items.length === 0 && <p className="empty">No users match these filters.</p>}
    </div>
    <div className="pagination">
      <button className="secondary" disabled={offset === 0} onClick={() => { setLoading(true); setOffset(Math.max(0, offset - 20)) }}>Previous</button>
      <span>{page.total ? `${offset + 1}–${Math.min(offset + page.items.length, page.total)} of ${page.total}` : '0 users'}</span>
      <button className="secondary" disabled={offset + 20 >= page.total} onClick={() => { setLoading(true); setOffset(offset + 20) }}>Next</button>
    </div>

    {showCreate && <div className="dialog-backdrop" role="presentation" onMouseDown={() => setShowCreate(false)}>
      <section className="dialog" role="dialog" aria-modal="true" aria-labelledby="create-heading" onMouseDown={(event) => event.stopPropagation()}>
        <div className="dialog-head"><h2 id="create-heading">Add user</h2><button className="text-button" onClick={() => setShowCreate(false)}>Close</button></div>
        <form onSubmit={(event) => void create(event)}>
          <label>Name<input name="name" required maxLength={120} /></label>
          <label>Email<input name="email" type="email" required maxLength={320} /></label>
          <label>Temporary password<input name="password" type="password" required minLength={8} autoComplete="new-password" /></label>
          <label>Role<select name="role">{roles.map((role) => <option key={role}>{role}</option>)}</select></label>
          {error && <p className="form-error" role="alert">{error}</p>}
          <button type="submit">Create user</button>
        </form>
      </section>
    </div>}

    {editing && <div className="dialog-backdrop" role="presentation" onMouseDown={() => setEditing(null)}>
      <section className="dialog" role="dialog" aria-modal="true" aria-labelledby="edit-heading" onMouseDown={(event) => event.stopPropagation()}>
        <div className="dialog-head"><h2 id="edit-heading">Edit user</h2><button className="text-button" onClick={() => setEditing(null)}>Close</button></div>
        <p className="muted">{editing.email}</p>
        <form onSubmit={(event) => void update(event)}>
          <label>Name<input name="name" required maxLength={120} defaultValue={editing.name} /></label>
          <label>Role<select name="role" defaultValue={editing.role}>{roles.map((role) => <option key={role}>{role}</option>)}</select></label>
          <label>Status<select name="is_active" defaultValue={String(editing.is_active)}><option value="true">Active</option><option value="false">Inactive</option></select></label>
          {error && <p className="form-error" role="alert">{error}</p>}
          <button type="submit">Save changes</button>
        </form>
      </section>
    </div>}
  </div>
}
