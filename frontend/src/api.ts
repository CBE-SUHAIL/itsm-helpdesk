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
  const response = await fetch(`${base}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init.headers },
  })
  if (!response.ok) {
    let message = `Request failed (${response.status})`
    try {
      const body = (await response.json()) as { detail?: string }
      if (typeof body.detail === 'string') message = body.detail
    } catch { /* An empty or non-JSON error still has its HTTP status. */ }
    throw new ApiError(response.status, message)
  }
  return (response.status === 204 ? undefined : await response.json()) as T
}

export function apiMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Something went wrong. Please try again.'
}
