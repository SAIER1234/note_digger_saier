"use client"

import { useEffect, useRef, useState } from "react"
import { Music, Loader2 } from "lucide-react"

interface Props {
  musicxmlUrl: string
  onReady?: () => void
}

export function ScoreViewer({ musicxmlUrl, onReady }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const osmdRef = useRef<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function loadScore() {
      setLoading(true)
      setError(null)

      try {
        // Dynamically import OSMD (it's a browser-only library)
        const { OpenSheetMusicDisplay } = await import("opensheetmusicdisplay")

        if (cancelled || !containerRef.current) return

        const osmd = new OpenSheetMusicDisplay(containerRef.current.id || "osmd-container", {
          autoResize: true,
          backend: "svg",
          drawTitle: false,
          drawSubtitle: false,
          drawComposer: false,
          pageBackgroundColor: "#1a1a24",
          pageFormat: "A4",
        })

        osmdRef.current = osmd

        // Fetch MusicXML and load
        const response = await fetch(musicxmlUrl)
        if (!response.ok) {
          throw new Error(`获取谱面数据失败 (${response.status})`)
        }
        const musicxml = await response.text()

        await osmd.load(musicxml)
        osmd.render()

        if (!cancelled) {
          setLoading(false)
          onReady?.()
        }
      } catch (err: any) {
        if (!cancelled) {
          setError(err.message || "加载谱面失败")
          setLoading(false)
        }
      }
    }

    loadScore()

    return () => {
      cancelled = true
      if (osmdRef.current) {
        osmdRef.current.clear?.()
        osmdRef.current = null
      }
    }
  }, [musicxmlUrl])

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center p-12 text-center">
        <Music className="w-12 h-12 text-[var(--text-muted)] mb-3" />
        <p className="text-[var(--text-muted)]">谱面加载失败</p>
        <p className="text-sm text-[var(--error)] mt-1">{error}</p>
      </div>
    )
  }

  return (
    <div className="relative">
      {loading && (
        <div className="absolute inset-0 flex items-center justify-center bg-[var(--surface)]/80 z-10 rounded-xl">
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="w-8 h-8 text-[var(--primary)] animate-spin" />
            <p className="text-sm text-[var(--text-muted)]">正在渲染谱面...</p>
          </div>
        </div>
      )}
      <div
        id="osmd-container"
        ref={containerRef}
        className="score-container w-full overflow-x-auto bg-[var(--surface)] rounded-xl p-4"
      />
    </div>
  )
}
