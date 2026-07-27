// Frontend auth client — login, register, token management.

import { getApiBase } from './api'

const TOKEN_KEY = 'nd_token'
const USER_KEY = 'nd_user'

export interface User {
  id: number
  email: string
  tier: 'free' | 'pro'
  pro_expires_at?: string | null
  usage_count: number
  usage_limit: number
}

// ── Token storage ──

export function getToken(): string | null {
  if (typeof window === 'undefined') return null
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

// ── User cache ──

export function getCachedUser(): User | null {
  if (typeof window === 'undefined') return null
  try {
    const raw = localStorage.getItem(USER_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function cacheUser(user: User): void {
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}

// ── API calls ──

export async function register(email: string, password: string): Promise<{ token: string; user: User }> {
  const base = getApiBase()
  const res = await fetch(`${base}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: '注册失败' }))
    throw new Error(err.detail || '注册失败')
  }

  const data = await res.json()
  setToken(data.token)
  cacheUser(data.user)
  return data
}

export async function login(email: string, password: string): Promise<{ token: string; user: User }> {
  const base = getApiBase()
  const res = await fetch(`${base}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: '登录失败' }))
    throw new Error(err.detail || '登录失败')
  }

  const data = await res.json()
  setToken(data.token)
  cacheUser(data.user)
  return data
}

export async function fetchMe(): Promise<User | null> {
  const token = getToken()
  if (!token) return null

  const base = getApiBase()
  const res = await fetch(`${base}/auth/me/token/${token}`)
  if (!res.ok) {
    clearToken()
    return null
  }

  const data = await res.json()
  cacheUser(data.user)
  return data.user
}

export async function activatePro(code: string): Promise<{ token: string; user: User; message: string }> {
  const token = getToken()
  if (!token) throw new Error('请先登录')

  const base = getApiBase()
  const res = await fetch(`${base}/auth/activate/token/${token}/code/${encodeURIComponent(code)}`, {
    method: 'POST',
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: '激活失败' }))
    throw new Error(err.detail || '激活失败')
  }

  const data = await res.json()
  setToken(data.token)
  cacheUser(data.user)
  return data
}

export async function getHistory(): Promise<any[]> {
  const token = getToken()
  if (!token) return []

  const base = getApiBase()
  const res = await fetch(`${base}/auth/history/${token}`)
  if (!res.ok) return []

  const data = await res.json()
  return data.history || []
}

export function logout(): void {
  clearToken()
  // Reload to reset all state
  window.location.href = '/'
}

export function isLoggedIn(): boolean {
  return !!getToken()
}

export function getUsageDisplay(user: User | null): string {
  if (!user) return ''
  if (user.tier === 'pro') return 'Pro'
  return `${user.usage_count}/${user.usage_limit} 次`
}

export function canTranscribe(user: User | null): boolean {
  if (!user) return false
  if (user.tier === 'pro') return true
  return user.usage_count < user.usage_limit
}
