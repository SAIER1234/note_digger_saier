"use client"

import { useParams, useRouter } from "next/navigation"
import { ArrowLeft, Download, Music, FileText, FileType, Volume2 } from "lucide-react"
import { useTranscription } from "@/hooks/useTranscription"
import { ScoreViewer } from "@/components/score/ScoreViewer"
import { ScoreEditor } from "@/components/score/ScoreEditor"
import { MidiPlayer } from "@/components/score/MidiPlayer"
import { getMidiUrl, getMusicXmlUrl, getPdfUrl, getAudioUrl } from "@/lib/api"
import { formatDuration } from "@/lib/utils"
import { toast } from "sonner"

export default function TranscriptionPage() {
  const params = useParams()
  const router = useRouter()
  const taskId = params.id as string

  const { status, error, stageLabel, percent, isLoading, isCompleted, result } =
    useTranscription({ taskId, pollInterval: 1500 })

  const musicxmlUrl = getMusicXmlUrl(taskId)
  const midiUrl = getMidiUrl(taskId)

  const handleExport = (url: string, label: string) => {
    window.open(url, "_blank")
    toast.success(`正在下载 ${label}`)
  }

  return (
    <main className="min-h-screen px-4 py-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <button
          onClick={() => router.push("/")}
          className="flex items-center gap-2 text-sm text-[var(--text-muted)] hover:text-[var(--text)] transition-colors cursor-pointer"
        >
          <ArrowLeft className="w-4 h-4" />
          返回首页
        </button>

        {isCompleted && (
          <span className="flex items-center gap-2 text-sm">
            <span className="flex items-center gap-1 text-[var(--success)]">
              <Music className="w-3 h-3" />
              扒谱完成
            </span>
            {result?.engine && (
              <span className="px-2 py-0.5 rounded text-xs bg-[var(--surface-light)] text-[var(--text-muted)]">
                {result.engine === "auto" ? "自动" : result.engine === "basic-pitch" ? "Basic Pitch" : result.engine === "simple" ? "快速" : result.engine}
              </span>
            )}
          </span>
        )}
      </div>

      {/* Loading state */}
      {isLoading && (
        <div className="flex flex-col items-center justify-center py-16 max-w-lg mx-auto">
          {/* Progress bar */}
          <div className="w-full mb-6">
            <div className="flex justify-between text-sm mb-2">
              <span className="text-[var(--text)] font-medium">{stageLabel}</span>
              <span className="text-[var(--primary-light)] font-mono">{percent}%</span>
            </div>
            <div className="w-full h-3 bg-[var(--surface-light)] rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-[var(--primary)] to-[var(--accent)] rounded-full transition-all duration-700 ease-out"
                style={{ width: `${Math.max(percent, 5)}%` }}
              />
            </div>
          </div>

          {/* Animated piano icon */}
          <div className="relative mb-4">
            <div className="w-16 h-16 border-3 border-[var(--surface-light)] border-t-[var(--primary)] rounded-full animate-spin" />
            <Music className="absolute inset-0 m-auto w-6 h-6 text-[var(--primary)]" />
          </div>

          <p className="text-sm text-[var(--text-muted)] text-center">
            {percent < 30 && "正在分析你的音频..."}
            {percent >= 30 && percent < 70 && "AI 正在识别音符，这可能需要几十秒..."}
            {percent >= 70 && percent < 100 && "正在生成五线谱，马上就好..."}
            {percent >= 100 && "处理完成！"}
          </p>
          {result?.metadata?.duration && (
            <p className="text-xs text-[var(--text-muted)] mt-2">
              音频时长: {formatDuration(result.metadata.duration)}
            </p>
          )}
        </div>
      )}

      {/* Error state */}
      {status === "failed" && (
        <div className="flex flex-col items-center justify-center py-16 md:py-24 text-center px-4">
          <div className="w-16 h-16 rounded-full bg-[var(--error)]/10 flex items-center justify-center mb-4">
            <Music className="w-8 h-8 text-[var(--error)]" />
          </div>
          <h2 className="text-lg md:text-xl font-semibold mb-2">扒谱失败</h2>
          <p className="text-sm text-[var(--text-muted)] mb-6 max-w-md">{error || "未知错误"}</p>
          <div className="flex gap-3">
            <button
              onClick={() => router.push("/")}
              className="px-6 py-2.5 rounded-xl bg-[var(--primary)] text-white hover:bg-[var(--primary-dark)] transition-colors cursor-pointer text-sm"
            >
              重新上传
            </button>
            <button
              onClick={() => window.location.reload()}
              className="px-6 py-2.5 rounded-xl bg-[var(--surface)] text-[var(--text)] border border-[var(--surface-light)] hover:bg-[var(--surface-light)] transition-colors cursor-pointer text-sm"
            >
              重试此任务
            </button>
          </div>
        </div>
      )}

      {/* Completed state */}
      {isCompleted && (
        <div className="space-y-6 animate-fade-in">
          {/* Metadata bar */}
          {result?.metadata && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 md:gap-3">
              {[
                { label: "音符数", value: result.metadata.total_notes ?? "-" },
                { label: "时长", value: formatDuration(result.metadata.duration_seconds ?? 0) },
                { label: "速度", value: result.metadata.tempo ? `${result.metadata.tempo} BPM` : "-" },
                { label: "音域", value: result.metadata.pitch_range ?? "-" },
              ].map((item) => (
                <div
                  key={item.label}
                  className="bg-[var(--surface)] rounded-xl p-2.5 md:p-3 text-center"
                >
                  <p className="text-xs text-[var(--text-muted)]">{item.label}</p>
                  <p className="text-sm font-semibold text-[var(--text)] mt-0.5">
                    {item.value}
                  </p>
                </div>
              ))}
            </div>
          )}

          {/* Arrangement badge */}
          {result?.arranged && (
            <div className="flex items-center gap-2 bg-[var(--accent)]/10 border border-[var(--accent)]/20 rounded-xl px-4 py-3">
              <span className="text-lg">🎹</span>
              <div>
                <p className="text-sm font-medium text-[var(--accent)]">自动编曲已启用</p>
                <p className="text-xs text-[var(--text-muted)]">
                  风格: {result.style === "broken" ? "分解和弦" : result.style === "arpeggio" ? "琶音" : result.style === "block" ? "柱式和弦" : result.style === "alberti" ? "阿尔贝蒂低音" : result.style === "waltz" ? "华尔兹" : result.style}
                </p>
              </div>
            </div>
          )}

          {/* Chords */}
          {result?.chord_line && (
            <div className="bg-[var(--surface)] rounded-xl p-4">
              <h3 className="text-xs font-medium text-[var(--text-muted)] mb-2">和弦进行</h3>
              <p className="text-sm font-mono text-[var(--accent)]">{result.chord_line}</p>
            </div>
          )}

          {/* Player */}
          <MidiPlayer taskId={taskId} />

          {/* Editor toolbar */}
          <ScoreEditor taskId={taskId} />

          {/* Sheet music */}
          <div className="bg-[var(--surface)] rounded-xl overflow-hidden">
            <ScoreViewer musicxmlUrl={musicxmlUrl} />
          </div>

          {/* Export buttons */}
          <div className="grid grid-cols-2 md:flex md:flex-wrap gap-2 md:gap-3 justify-center">
            {[
              { url: getPdfUrl(taskId), label: "PDF 谱面", icon: FileText },
              { url: getMusicXmlUrl(taskId), label: "MusicXML", icon: FileType },
              { url: getMidiUrl(taskId), label: "MIDI", icon: Music },
              { url: getAudioUrl(taskId), label: "MP3", icon: Volume2 },
            ].map(({ url, label, icon: Icon }) => (
              <button
                key={label}
                onClick={() => handleExport(url, label)}
                className="flex items-center justify-center gap-1.5 md:gap-2 px-3 md:px-5 py-2 md:py-2.5 rounded-xl bg-[var(--surface)] text-[var(--text)] hover:bg-[var(--surface-light)] transition-all cursor-pointer text-xs md:text-sm"
              >
                <Icon className="w-3.5 h-3.5 md:w-4 md:h-4" />
                {label}
              </button>
            ))}
          </div>
        </div>
      )}
    </main>
  )
}
