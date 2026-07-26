"use client"

import { useState } from "react"
import { Link, Music } from "lucide-react"

interface Props {
  onSubmit: (url: string) => void
  loading: boolean
}

export function UrlInput({ onSubmit, loading }: Props) {
  const [url, setUrl] = useState("")

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (url.trim() && !loading) {
      onSubmit(url.trim())
    }
  }

  const isValidUrl = url.trim().length > 0

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <div className="relative">
        <Link className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-[var(--text-muted)]" />
        <input
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="粘贴 YouTube 或 B站链接..."
          className="w-full pl-12 pr-4 py-4 bg-[var(--surface-light)] border border-[var(--surface-light)] rounded-xl text-[var(--text)] placeholder:text-[var(--text-muted)] focus:outline-none focus:border-[var(--primary)] transition-colors"
        />
      </div>

      <p className="text-xs text-[var(--text-muted)] -mt-2">
        支持 youtube.com、bilibili.com 视频链接
      </p>

      <button
        type="submit"
        disabled={!isValidUrl || loading}
        className="w-full py-3 rounded-xl font-medium transition-all cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed bg-[var(--primary)] text-white hover:bg-[var(--primary-dark)] active:scale-[0.98]"
      >
        {loading ? (
          <span className="flex items-center justify-center gap-2">
            <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
            下载并处理中...
          </span>
        ) : (
          <span className="flex items-center justify-center gap-2">
            <Music className="w-4 h-4" />
            从链接扒谱
          </span>
        )}
      </button>
    </form>
  )
}
