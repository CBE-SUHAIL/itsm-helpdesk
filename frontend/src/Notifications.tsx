import { useEffect, useState } from 'react'
import { apiMessage } from './api'
import type { Notification, Page } from './api'
import { useAuth } from './authContext'

export function Notifications({ onTicket }: { onTicket: (id: string) => void }) {
  const { request } = useAuth()
  const [page, setPage] = useState<Page<Notification>>({ items: [], total: 0 })
  const [offset, setOffset] = useState(0)
  const [unreadOnly, setUnreadOnly] = useState(false)
  const [includeDismissed, setIncludeDismissed] = useState(false)
  const [revision, setRevision] = useState(0)
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    const query = new URLSearchParams({ limit: '20', offset: String(offset), unread_only: String(unreadOnly), include_dismissed: String(includeDismissed) })
    const load = () => void request<Page<Notification>>(`/notifications?${query}`).then((result) => { if (active) { setPage(result); setError('') } }).catch((cause) => { if (active) setError(apiMessage(cause)) })
    load()
    const timer = window.setInterval(load, 15000)
    return () => { active = false; window.clearInterval(timer) }
  }, [request, offset, unreadOnly, includeDismissed, revision])
  async function update(id: string, action: 'read' | 'dismiss') {
    try { await request(`/notifications/${id}/${action}`, { method: 'PATCH' }); setRevision((value) => value + 1) }
    catch (cause) { setError(apiMessage(cause)) }
  }
  return <div className="content-width"><div className="page-heading"><div><span className="eyebrow">UPDATES</span><h1>Notifications</h1><p>Ticket activity appears here automatically.</p></div></div>
    <div className="filter-bar"><label><input type="checkbox" checked={unreadOnly} onChange={(event) => { setUnreadOnly(event.target.checked); setOffset(0) }} /> Unread only</label><label><input type="checkbox" checked={includeDismissed} onChange={(event) => { setIncludeDismissed(event.target.checked); setOffset(0) }} /> Include dismissed</label><span className="result-count">{page.total} notifications</span></div>
    {error && <p className="form-error" role="alert">{error}</p>}
    <div className="panel">{page.items.map((item) => <div className="feed-item notification" key={item.id}><div><span className={`pill ${item.read_at ? 'inactive' : 'active'}`}>{item.read_at ? 'Read' : 'New'}</span><p>{item.message}</p><small>{new Date(item.created_at).toLocaleString()}</small></div><div className="row-actions">{item.ticket_id && <button className="text-button" onClick={() => onTicket(item.ticket_id!)}>Open ticket</button>}{!item.read_at && <button className="secondary" onClick={() => void update(item.id, 'read')}>Mark read</button>}{!item.dismissed_at && <button className="text-button" onClick={() => void update(item.id, 'dismiss')}>Dismiss</button>}</div></div>)}{page.items.length === 0 && <p className="empty">No notifications to show.</p>}</div>
    <div className="pagination"><button className="secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 20))}>Previous</button><span>{page.total ? `${offset + 1}–${Math.min(offset + page.items.length, page.total)} of ${page.total}` : '0 notifications'}</span><button className="secondary" disabled={offset + 20 >= page.total} onClick={() => setOffset(offset + 20)}>Next</button></div>
  </div>
}
