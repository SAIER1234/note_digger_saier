"use client"

import { useState, useRef, useEffect } from "react"
import { logout, activatePro, getUsageDisplay, type User } from "@/lib/auth"

interface UserMenuProps {
  user: User
  onUpdate: (user: User) => void
}

export function UserMenu({ user, onUpdate }: UserMenuProps) {
  const [open, setOpen] = useState(false)
  const [activating, setActivating] = useState(false)
  const [code, setCode] = useState("")
  const [codeError, setCodeError] = useState("")
  const [showCodeInput, setShowCodeInput] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [])

  const handleActivate = async () => {
    setCodeError("")
    setActivating(true)
    try {
      const result = await activatePro(code)
      onUpdate(result.user)
      setShowCodeInput(false)
      setCode("")
    } catch (err: any) {
      setCodeError(err.message || "激活失败")
    } finally {
      setActivating(false)
    }
  }

  return (
    <div className="relative" ref={menuRef}>
      <button
        onClick={() => setOpen(!open)}
        className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all cursor-pointer ${
          user.tier === "pro"
            ? "bg-amber-500/10 text-amber-400 border border-amber-500/20 hover:bg-amber-500/20"
            : "bg-[var(--surface)] text-[var(--text-muted)] border border-[var(--surface-light)] hover:text-[var(--text)]"
        }`}
      >
        <span className="w-2 h-2 rounded-full bg-[var(--success)]" />
        <span className="truncate max-w-[140px]">{user.email}</span>
        <span className={user.tier === "pro" ? "text-amber-400" : "text-[var(--text-muted)]"}>
          {user.tier === "pro" ? "Pro" : getUsageDisplay(user)}
        </span>
        <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="m6 9 6 6 6-6"/>
        </svg>
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-64 bg-[var(--surface)] rounded-xl border border-[var(--surface-light)] shadow-xl z-50 overflow-hidden">
          {/* User info */}
          <div className="px-4 py-3 border-b border-[var(--surface-light)]">
            <p className="text-sm text-[var(--text)] truncate">{user.email}</p>
            <p className="text-xs text-[var(--text-muted)]">
              {user.tier === "pro" ? "Pro 无限使用" : `免费版 · ${getUsageDisplay(user)}`}
              {user.pro_expires_at && (
                <span className="ml-1 text-amber-400">
                  ({new Date(user.pro_expires_at).toLocaleDateString("zh-CN")} 到期)
                </span>
              )}
            </p>
          </div>

          {/* Activation code section */}
          {user.tier !== "pro" && (
            <div className="px-4 py-3 border-b border-[var(--surface-light)]">
              {!showCodeInput ? (
                <button
                  onClick={() => setShowCodeInput(true)}
                  className="w-full text-left text-xs text-[var(--accent)] hover:text-[var(--primary-light)] cursor-pointer transition-colors"
                >
                  ✨ 使用激活码升级 Pro
                </button>
              ) : (
                <div className="flex flex-col gap-2">
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={code}
                      onChange={(e) => setCode(e.target.value)}
                      placeholder="输入激活码"
                      className="flex-1 px-3 py-1.5 rounded-lg bg-[var(--surface-light)] text-[var(--text)] text-xs placeholder:text-[var(--text-muted)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)] border border-transparent focus:border-[var(--accent)]"
                    />
                    <button
                      onClick={handleActivate}
                      disabled={activating || !code.trim()}
                      className="px-3 py-1.5 rounded-lg bg-[var(--accent)] text-white text-xs font-medium hover:opacity-90 disabled:opacity-40 cursor-pointer transition-all"
                    >
                      {activating ? "..." : "激活"}
                    </button>
                  </div>
                  {codeError && (
                    <p className="text-xs text-[var(--error)]">{codeError}</p>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Actions */}
          <div className="px-1 py-1">
            <a
              href="/history"
              className="block px-3 py-2 text-sm text-[var(--text)] hover:bg-[var(--surface-light)] rounded-lg transition-colors cursor-pointer"
            >
              📋 我的历史
            </a>
            <button
              onClick={() => { logout() }}
              className="w-full text-left px-3 py-2 text-sm text-[var(--text-muted)] hover:bg-[var(--surface-light)] rounded-lg transition-colors cursor-pointer"
            >
              🚪 退出登录
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
