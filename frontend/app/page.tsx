"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { toast } from "sonner"
import { FileUpload } from "@/components/upload/FileUpload"
import { UrlInput } from "@/components/upload/UrlInput"
import { Recorder } from "@/components/upload/Recorder"
import { uploadFile, transcribeUrl, uploadRecording } from "@/lib/api"
import { getFreeUsesRemaining, getTierLabel } from "@/lib/freemium"

type InputMode = "file" | "url" | "record"
type ModelChoice = "auto" | "aria-amt" | "basic-pitch" | "simple"

const MODELS: { key: ModelChoice; label: string; desc: string }[] = [
  { key: "auto", label: "自动", desc: "智能选择最优引擎" },
  { key: "aria-amt", label: "Aria-AMT Pro", desc: "云端GPU · 专业级" },
  { key: "basic-pitch", label: "Basic Pitch", desc: "Spotify AI · 高准确度" },
  { key: "simple", label: "快速", desc: "极速处理 · 基础质量" },
]

export default function Home() {
  const router = useRouter()
  const [mode, setMode] = useState<InputMode>("file")
  const [model, setModel] = useState<ModelChoice>("auto")
  const [loading, setLoading] = useState(false)
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null)
  const [tierLabel, setTierLabel] = useState("")
  const [arrange, setArrange] = useState(false)
  const [arrStyle, setArrStyle] = useState("broken")

  useEffect(() => {
    setTierLabel(getTierLabel())
    // Check backend connectivity
    fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/`)
      .then(r => r.json())
      .then(() => setBackendOnline(true))
      .catch(() => setBackendOnline(false))
  }, [])

  const handleFileSelect = async (file: File) => {
    setLoading(true)
    try {
      const result = await uploadFile(file, model, arrange, arrStyle)
      router.push(`/transcription/${result.task_id}`)
    } catch (err: any) {
      toast.error(err.message || "上传失败，请重试")
      setLoading(false)
    }
  }

  const handleUrlSubmit = async (url: string) => {
    setLoading(true)
    try {
      const result = await transcribeUrl(url, model, arrange, arrStyle)
      router.push(`/transcription/${result.task_id}`)
    } catch (err: any) {
      toast.error(err.message || "提交失败，请检查链接")
      setLoading(false)
    }
  }

  const handleRecordingComplete = async (blob: Blob) => {
    setLoading(true)
    try {
      const result = await uploadRecording(blob, model, arrange, arrStyle)
      router.push(`/transcription/${result.task_id}`)
    } catch (err: any) {
      toast.error(err.message || "上传录音失败")
      setLoading(false)
    }
  }

  const tabs: { key: InputMode; label: string }[] = [
    { key: "file", label: "上传文件" },
    { key: "url", label: "粘贴链接" },
    { key: "record", label: "录制音频" },
  ]

  return (
    <main className="min-h-screen flex flex-col items-center justify-center px-4 py-16">
      {/* Hero */}
      <div className="text-center mb-8">
        <h1 className="text-4xl md:text-5xl font-bold mb-3">
          <span className="bg-gradient-to-r from-[var(--primary-light)] via-[var(--accent)] to-[var(--primary)] bg-clip-text text-transparent">
            Note Digger
          </span>
        </h1>
        <p className="text-lg text-[var(--text-muted)] max-w-md mx-auto">
          AI 自动钢琴扒谱 — 上传音频，秒出五线谱
        </p>
        <div className="flex items-center justify-center gap-3 mt-2">
          <p className="text-xs text-[var(--text-muted)]">
            {tierLabel || "加载中..."}
          </p>
          {backendOnline !== null && (
            <span className={`flex items-center gap-1 text-xs ${backendOnline ? "text-[var(--success)]" : "text-[var(--error)]"}`}>
              <span className={`w-1.5 h-1.5 rounded-full ${backendOnline ? "bg-[var(--success)]" : "bg-[var(--error)]"}`} />
              {backendOnline ? "服务在线" : "后端离线"}
            </span>
          )}
        </div>
      </div>

      {/* Input Card */}
      <div className="w-full max-w-xl">
        {/* Mode Tabs */}
        <div className="flex border-b border-[var(--surface-light)]">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setMode(tab.key)}
              className={`px-5 py-3 text-sm font-medium transition-colors relative cursor-pointer ${
                mode === tab.key
                  ? "text-[var(--primary-light)]"
                  : "text-[var(--text-muted)] hover:text-[var(--text)]"
              }`}
            >
              {tab.label}
              {mode === tab.key && (
                <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-[var(--primary)]" />
              )}
            </button>
          ))}
        </div>

        {/* Input Area */}
        <div className="bg-[var(--surface)] border border-[var(--surface-light)] border-t-0 rounded-b-2xl p-6 md:p-8">
          {mode === "file" && (
            <FileUpload onFile={handleFileSelect} loading={loading} />
          )}
          {mode === "url" && (
            <UrlInput onSubmit={handleUrlSubmit} loading={loading} />
          )}
          {mode === "record" && (
            <Recorder onComplete={handleRecordingComplete} loading={loading} />
          )}
        </div>

        {/* Model selector */}
        <div className="flex items-center justify-center gap-2 mt-4">
          <span className="text-xs text-[var(--text-muted)]">引擎:</span>
          {MODELS.map((m) => (
            <button
              key={m.key}
              onClick={() => setModel(m.key)}
              className={`px-3 py-1 rounded-lg text-xs font-medium transition-all cursor-pointer ${
                model === m.key
                  ? "bg-[var(--primary)] text-white"
                  : "bg-[var(--surface)] text-[var(--text-muted)] hover:text-[var(--text)] border border-[var(--surface-light)]"
              }`}
              title={m.desc}
            >
              {m.label}
            </button>
          ))}
        </div>

        {/* Arrangement toggle */}
        <div className="flex items-center justify-center gap-3 mt-4">
          <label className="flex items-center gap-2 text-xs text-[var(--text-muted)] cursor-pointer">
            <input
              type="checkbox"
              checked={arrange}
              onChange={(e) => setArrange(e.target.checked)}
              className="w-3.5 h-3.5 accent-[var(--primary)] cursor-pointer"
            />
            自动编曲
          </label>
          {arrange && (
            <select
              value={arrStyle}
              onChange={(e) => setArrStyle(e.target.value)}
              className="bg-[var(--surface-light)] text-xs text-[var(--text)] px-2 py-1 rounded border border-[var(--surface-light)] cursor-pointer"
            >
              <option value="broken">分解和弦</option>
              <option value="arpeggio">琶音</option>
              <option value="block">柱式和弦</option>
              <option value="alberti">阿尔贝蒂低音</option>
            </select>
          )}
        </div>

        <p className="text-xs text-[var(--text-muted)] text-center mt-3">
          支持 MP3 / WAV / FLAC / M4A · 钢琴独奏最佳{arrange && " · 自动编曲已启用"}
        </p>
      </div>

      {/* Loading overlay */}
      {loading && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="bg-[var(--surface)] rounded-2xl p-8 text-center shadow-2xl animate-fade-in">
            <div className="w-12 h-12 border-4 border-[var(--primary)] border-t-transparent rounded-full animate-spin mx-auto mb-4" />
            <p className="text-[var(--text)] font-medium">正在提交音频...</p>
            <p className="text-sm text-[var(--text-muted)] mt-1">AI 模型准备中</p>
          </div>
        </div>
      )}
    </main>
  )
}
