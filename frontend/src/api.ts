export type Role = 'Employee' | 'Support agent' | 'Admin'

export type User = {
  id: string
  name: string
  email: string
  role: Role
  is_active: boolean
  created_at: string
  updated_at: string
}

export type UserPage = { items: User[]; total: number }
export type Page<T> = { items: T[]; total: number }
export type Category = { id: string; name: string; description: string; is_active: boolean; created_at: string; updated_at: string }
export type TicketStatus = 'Open' | 'Assigned' | 'In Progress' | 'Resolved' | 'Closed'
export type Priority = 'Low' | 'Medium' | 'High' | 'Critical'
export type Ticket = {
  id: string; title: string; description: string; category_id: string; creator_id: string
  assignee_id: string | null; status: TicketStatus; priority: Priority
  response_due_at: string; resolution_due_at: string; first_response_at: string | null
  resolved_at: string | null; response_overdue: boolean; resolution_overdue: boolean
  created_at: string; updated_at: string
}
export type Comment = { id: string; ticket_id: string; author_id: string; body: string; created_at: string }
export type TicketHistory = { id: string; ticket_id: string; actor_id: string; field: string; old_value: string | null; new_value: string | null; reason: string | null; created_at: string }
export type Attachment = { id: string; ticket_id: string; uploader_id: string; file_name: string; content_type: string; size_bytes: number; created_at: string }
export type Notification = { id: string; recipient_id: string; ticket_id: string | null; type: string; message: string; read_at: string | null; dismissed_at: string | null; created_at: string }
export type Article = { id: string; title: string; body: string; category_id: string; author_id: string; is_published: boolean; created_at: string; updated_at: string }
export type Dashboard = { counts_by_status: Record<string, number>; counts_by_priority: Record<string, number>; response_overdue_count: number; resolution_overdue_count: number; agent_workload: Record<string, number> | null }
export type SlaTarget = { first_response_hours: number; resolution_hours: number }
export type Settings = { sla_targets: Record<Priority, SlaTarget>; max_attachment_bytes: number; allowed_attachment_types: string[] }
export type AuditLog = { id: string; actor_id: string | null; action: string; entity_type: string; entity_id: string | null; old_value: Record<string, unknown> | null; new_value: Record<string, unknown> | null; created_at: string }
export type TokenPair = {
  access_token: string
  refresh_token: string
  token_type: 'bearer'
}
export type LoginResult = TokenPair & { user: User }

const base = '/api/v1'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export async function jsonRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const jsonBody = typeof init.body === 'string'
  const response = await fetch(`${base}${path}`, {
    ...init,
    headers: { ...(jsonBody ? { 'Content-Type': 'application/json' } : {}), ...init.headers },
  })
  if (!response.ok) {
    let message = `Request failed (${response.status})`
    try {
      const body = (await response.json()) as { detail?: string }
      if (typeof body.detail === 'string') message = body.detail
    } catch { /* An empty or non-JSON error still has its HTTP status. */ }
    throw new ApiError(response.status, message)
  }
  if (response.status === 204) return undefined as T
  const contentType = response.headers.get('content-type') ?? ''
  if (contentType.startsWith('application/pdf') || contentType.startsWith('text/csv') ||
      contentType.startsWith('image/') || contentType.startsWith('text/plain') ||
      contentType.startsWith('application/octet-stream')) return await response.blob() as T
  return await response.json() as T
}

export function apiMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Something went wrong. Please try again.'
}
