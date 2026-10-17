import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { apiMessage } from './api'
import type { Article, Category, Page } from './api'
import { useAuth } from './authContext'

export function KnowledgeBase() {
  const { request, user } = useAuth()
  const [page, setPage] = useState<Page<Article>>({ items: [], total: 0 })
  const [categories, setCategories] = useState<Category[]>([])
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('')
  const [offset, setOffset] = useState(0)
  const [selected, setSelected] = useState<Article | null>(null)
  const [editing, setEditing] = useState<Article | 'new' | null>(null)
  const [revision, setRevision] = useState(0)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  useEffect(() => { void request<Page<Category>>('/categories?limit=100').then((value) => setCategories(value.items)).catch((cause) => setError(apiMessage(cause))) }, [request])
  useEffect(() => {
    let active = true
    const query = new URLSearchParams({ limit: '20', offset: String(offset) })
    if (search.trim()) query.set('q', search.trim())
    if (category) query.set('category_id', category)
    void request<Page<Article>>(`/articles?${query}`).then((value) => { if (active) setPage(value) }).catch((cause) => { if (active) setError(apiMessage(cause)) })
    return () => { active = false }
  }, [request, search, category, offset, revision])
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!editing) return
    const data = new FormData(event.currentTarget)
    const body = { title: data.get('title'), body: data.get('body'), category_id: data.get('category_id') }
    try {
      const article = await request<Article>(editing === 'new' ? '/articles' : `/articles/${editing.id}`, { method: editing === 'new' ? 'POST' : 'PATCH', body: JSON.stringify(body) })
      setEditing(null); setSelected(article); setNotice('Article saved.'); setRevision((value) => value + 1); setError('')
    } catch (cause) { setError(apiMessage(cause)) }
  }
  async function publish(article: Article) {
    try {
      const result = await request<Article>(`/articles/${article.id}/publish`, { method: 'POST', body: JSON.stringify({ published: !article.is_published }) })
      setSelected(result); setRevision((value) => value + 1); setNotice(result.is_published ? 'Article published.' : 'Article unpublished.'); setError('')
    } catch (cause) { setError(apiMessage(cause)) }
  }
  return <div className="content-width"><div className="page-heading"><div><span className="eyebrow">HELP ARTICLES</span><h1>Knowledge base</h1><p>Find answers and share support guidance.</p></div>{user?.role !== 'Employee' && <button onClick={() => { setEditing('new'); setError('') }}>New article</button>}</div>
    <div className="filter-bar"><label>Search<input value={search} onChange={(event) => { setSearch(event.target.value); setOffset(0) }} placeholder="Search articles" /></label><label>Category<select value={category} onChange={(event) => { setCategory(event.target.value); setOffset(0) }}><option value="">All categories</option>{categories.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><span className="result-count">{page.total} articles</span></div>
    {error && <p className="form-error" role="alert">{error}</p>}{notice && <p className="form-success" role="status">{notice}</p>}
    <div className="two-column"><div className="panel">{page.items.map((article) => <button className="article-link" key={article.id} onClick={() => setSelected(article)}><strong>{article.title}</strong><small>{categories.find((item) => item.id === article.category_id)?.name ?? 'Category'} · {article.is_published ? 'Published' : 'Draft'}</small></button>)}{page.items.length === 0 && <p className="empty">No articles found.</p>}</div>
      <section className="panel article-body">{selected ? <><span className="eyebrow">{selected.is_published ? 'PUBLISHED' : 'DRAFT'}</span><h2>{selected.title}</h2><p>{selected.body}</p><small>Updated {new Date(selected.updated_at).toLocaleString()}</small><div className="row-actions">{(user?.role === 'Admin' || (user?.role === 'Support agent' && selected.author_id === user.id && !selected.is_published)) && <button className="secondary" onClick={() => setEditing(selected)}>Edit</button>}{user?.role === 'Admin' && <button onClick={() => void publish(selected)}>{selected.is_published ? 'Unpublish' : 'Publish'}</button>}</div></> : <p className="muted">Select an article to read it.</p>}</section></div>
    <div className="pagination"><button className="secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 20))}>Previous</button><span>{page.total ? `${offset + 1}–${Math.min(offset + page.items.length, page.total)} of ${page.total}` : '0 articles'}</span><button className="secondary" disabled={offset + 20 >= page.total} onClick={() => setOffset(offset + 20)}>Next</button></div>
    {editing && <div className="dialog-backdrop" role="presentation" onMouseDown={() => setEditing(null)}><section className="dialog" role="dialog" aria-modal="true" aria-labelledby="article-heading" onMouseDown={(event) => event.stopPropagation()}><div className="dialog-head"><h2 id="article-heading">{editing === 'new' ? 'New article' : 'Edit article'}</h2><button className="text-button" onClick={() => setEditing(null)}>Close</button></div><form onSubmit={(event) => void save(event)}><label>Title<input name="title" required maxLength={200} defaultValue={editing === 'new' ? '' : editing.title} /></label><label>Category<select name="category_id" required defaultValue={editing === 'new' ? '' : editing.category_id}><option value="" disabled>Choose</option>{categories.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Body<textarea name="body" rows={8} required defaultValue={editing === 'new' ? '' : editing.body} /></label>{error && <p className="form-error" role="alert">{error}</p>}<button>Save draft</button></form></section></div>}
  </div>
}
