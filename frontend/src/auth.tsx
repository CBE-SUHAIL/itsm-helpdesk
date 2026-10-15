import { useCallback, useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { ApiError, jsonRequest } from './api'
import type { LoginResult, TokenPair, User } from './api'
import { AuthContext } from './authContext'

const refreshKey = 'itsm-demo-refresh-token'
let refreshInFlight: Promise<TokenPair> | null = null

function rotateRefresh(): Promise<TokenPair> {
  if (refreshInFlight) return refreshInFlight
  const stored = localStorage.getItem(refreshKey)
  if (!stored) return Promise.reject(new ApiError(401, 'Login required'))
  refreshInFlight = jsonRequest<TokenPair>('/auth/refresh', {
    method: 'POST', body: JSON.stringify({ refresh_token: stored }),
  }).then((pair) => {
    localStorage.setItem(refreshKey, pair.refresh_token)
    return pair
  }).finally(() => { refreshInFlight = null })
  return refreshInFlight
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(() => Boolean(localStorage.getItem(refreshKey)))
  const access = useRef<string | null>(null)

  const clear = useCallback(() => {
    access.current = null
    localStorage.removeItem(refreshKey)
    setUser(null)
  }, [])

  const request = useCallback(async <T,>(path: string, init: RequestInit = {}): Promise<T> => {
    if (!access.current) throw new ApiError(401, 'Login required')
    const send = (token: string) => jsonRequest<T>(path, {
      ...init, headers: { ...init.headers, Authorization: `Bearer ${token}` },
    })
    try {
      return await send(access.current)
    } catch (error) {
      if (!(error instanceof ApiError) || error.status !== 401) throw error
      try {
        const pair = await rotateRefresh()
        access.current = pair.access_token
        const profile = await jsonRequest<User>('/users/me', {
          headers: { Authorization: `Bearer ${pair.access_token}` },
        })
        setUser(profile)
      } catch (retryError) {
        clear()
        throw retryError
      }
      try { return await send(access.current) }
      catch (retryError) {
        if (retryError instanceof ApiError && retryError.status === 401) clear()
        throw retryError
      }
    }
  }, [clear])

  useEffect(() => {
    let active = true
    if (!localStorage.getItem(refreshKey)) {
      return
    }
    rotateRefresh().then(async (pair) => {
      const profile = await jsonRequest<User>('/users/me', {
        headers: { Authorization: `Bearer ${pair.access_token}` },
      })
      if (active) {
        access.current = pair.access_token
        setUser(profile)
      }
    }).catch(() => { if (active) clear() })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [clear])

  const login = useCallback(async (email: string, password: string) => {
    const result = await jsonRequest<LoginResult>('/auth/login', {
      method: 'POST', body: JSON.stringify({ email, password }),
    })
    access.current = result.access_token
    localStorage.setItem(refreshKey, result.refresh_token)
    setUser(result.user)
  }, [])

  const logout = useCallback(async () => {
    let token = access.current
    let refresh = localStorage.getItem(refreshKey)
    try {
      if (token && refresh) {
        const revoke = () => jsonRequest('/auth/logout', {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
          body: JSON.stringify({ refresh_token: refresh }),
        })
        try { await revoke() }
        catch (error) {
          if (!(error instanceof ApiError) || error.status !== 401) throw error
          const pair = await rotateRefresh()
          token = pair.access_token
          refresh = pair.refresh_token
          await revoke()
        }
      }
    } finally { clear() }
  }, [clear])

  return <AuthContext.Provider value={{ user, loading, login, logout, request }}>
    {children}
  </AuthContext.Provider>
}
