"use client"

import { useState } from "react"
import { login, register, type User } from "@/lib/auth"

interface AuthModalProps {
  open: boolean
  onClose: () => void
  onAuth: (user: User) => void
}

export function AuthModal({ open, onClose, onAuth }: AuthModalProps) {
  const [tab, setTab] = useState<"login" | "register">("login")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)

  if (!open) return null

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")
    setLoading(true)

    try {
      const result = tab === "login"
        ? await login(email, password)
        : await register(email, password)
      onAuth(result.user)
      onClose()
      setEmail("")
      setPassword("")
    } catch (err: any) {
      setError(err.message || "操作失败")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="bg-[var(--surface)] rounded-2xl p-8 w-full max-w-md shadow-2xl border border-[var(--surface-light)]">
        {/* Tabs */}
        <div className="flex border-b border-[var(--surface-light)] mb-6">
          <button
            onClick={() => { setTab("login"); setError("") }}
            className={`px-4 py-2 text-sm font-medium transition-colors relative cursor-pointer ${
              tab === "login" ? "text-[var(--primary-light)]" : "text-[var(--text-muted)] hover:text-[var(--text)]"
            }`}
          >
            登录
            {tab === "login" && <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-[var(--primary)]" />}
          </button>
          <button
            onClick={() => { setTab("register"); setError("") }}
            className={`px-4 py-2 text-sm font-medium transition-colors relative cursor-pointer ${
              tab === "register" ? "text-[var(--primary-light)]" : "text-[var(--text-muted)] hover:text-[var(--text)]"
            }`}
          >
            注册
            {tab === "register" && <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-[var(--primary)]" />}
          </button>
          <button
            onClick={onClose}
            className="ml-auto text-[var(--text-muted)] hover:text-[var(--text)] cursor-pointer transition-colors"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <label className="block text-xs text-[var(--text-muted)] mb-1">邮箱</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="your@email.com"
              required
              className="w-full px-4 py-3 rounded-xl bg-[var(--surface-light)] text-[var(--text)] placeholder:text-[var(--text-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--primary)] border border-transparent focus:border-[var(--primary-light)] transition-all text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-[var(--text-muted)] mb-1">密码</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={tab === "register" ? "至少6个字符" : "输入密码"}
              required
              minLength={6}
              className="w-full px-4 py-3 rounded-xl bg-[var(--surface-light)] text-[var(--text)] placeholder:text-[var(--text-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--primary)] border border-transparent focus:border-[var(--primary-light)] transition-all text-sm"
            />
          </div>

          {error && (
            <p className="text-xs text-[var(--error)] bg-red-50 dark:bg-red-950/20 px-3 py-2 rounded-lg">{error}</p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 rounded-xl font-medium transition-all cursor-pointer bg-[var(--primary)] text-white hover:bg-[var(--primary-dark)] active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed text-sm"
          >
            {loading ? "处理中..." : tab === "login" ? "登录" : "注册"}
          </button>
        </form>

        {tab === "register" && (
          <p className="text-xs text-[var(--text-muted)] text-center mt-4">
            注册即送 <span className="text-[var(--accent)] font-medium">3 次</span> 免费扒谱
          </p>
        )}
      </div>
    </div>
  )
}
