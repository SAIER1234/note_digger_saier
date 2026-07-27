"use client"

import { useState, useEffect } from "react"
import Link from "next/link"
import { getHistory, getCachedUser, fetchMe, type User } from "@/lib/auth"

export default function HistoryPage() {
  const [user, setUser] = useState<User | null>(null)
  const [history, setHistory] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const cached = getCachedUser()
    if (cached) setUser(cached)
    fetchMe().then(u => {
      if (u) {
        setUser(u)
        loadHistory()
      } else {
        setLoading(false)
      }
    })
  }, [])

  const loadHistory = async () => {
    try {
      const h = await getHistory()
      setHistory(h)
    } catch {
      // ignore
    }
    setLoading(false)
  }

  if (loading) {
    return (
      <main className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-[var(--primary)] border-t-transparent rounded-full animate-spin" />
      </main>
    )
  }

  if (!user) {
    return (
      <main className="min-h-screen flex flex-col items-center justify-center px-4">
        <p className="text-[var(--text-muted)] mb-4">请先登录查看历史记录</p>
        <Link href="/" className="text-[var(--accent)] hover:text-[var(--primary-light)] text-sm transition-colors">
          ← 返回首页登录
        </Link>
      </main>
    )
  }

  return (
    <main className="min-h-screen px-4 py-8 max-w-2xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text)]">我的历史</h1>
          <p className="text-sm text-[var(--text-muted)] mt-1">
            {user.tier === "pro" ? "Pro · 无限使用" : `免费版 · ${user.usage_count}/${user.usage_limit} 次`}
          </p>
        </div>
        <Link
          href="/"
          className="px-4 py-2 rounded-lg text-sm font-medium transition-all cursor-pointer bg-[var(--surface)] text-[var(--text-muted)] border border-[var(--surface-light)] hover:text-[var(--text)]"
        >
          ← 返回
        </Link>
      </div>

      {/* History List */}
      {history.length === 0 ? (
        <div className="text-center py-16">
          <div className="text-4xl mb-4">🎹</div>
          <p className="text-[var(--text-muted)]">还没有扒谱记录</p>
          <Link
            href="/"
            className="inline-block mt-4 px-6 py-2 rounded-lg text-sm font-medium bg-[var(--primary)] text-white hover:bg-[var(--primary-dark)] transition-all cursor-pointer"
          >
            去扒一首
          </Link>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {history.map((item: any) => (
            <Link
              key={item.id}
              href={`/transcription/${item.task_id}`}
              className="flex items-center justify-between bg-[var(--surface)] border border-[var(--surface-light)] rounded-xl p-4 hover:border-[var(--primary-light)] hover:bg-[var(--surface-light)]/50 transition-all cursor-pointer"
            >
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-[var(--surface-light)] flex items-center justify-center text-lg">
                  🎼
                </div>
                <div>
                  <p className="text-sm font-medium text-[var(--text)]">
                    {item.original_filename || "未命名"}
                  </p>
                  <p className="text-xs text-[var(--text-muted)]">
                    {item.engine || "auto"} · {new Date(item.created_at).toLocaleDateString("zh-CN")}
                  </p>
                </div>
              </div>
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-[var(--text-muted)]">
                <path d="m9 18 6-6-6-6"/>
              </svg>
            </Link>
          ))}
        </div>
      )}
    </main>
  )
}
