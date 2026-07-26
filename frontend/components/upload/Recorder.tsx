"use client"

import { useState, useRef, useCallback } from "react"
import { Mic, Square, Play, Music } from "lucide-react"
import { formatDuration } from "@/lib/utils"

interface Props {
  onComplete: (blob: Blob) => void
  loading: boolean
}

export function Recorder({ onComplete, loading }: Props) {
  const [recording, setRecording] = useState(false)
  const [paused, setPaused] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const [audioUrl, setAudioUrl] = useState<string | null>(null)
  const [recordedBlob, setRecordedBlob] = useState<Blob | null>(null)

  const mediaRecorder = useRef<MediaRecorder | null>(null)
  const chunks = useRef<Blob[]>([])
  const timer = useRef<number | null>(null)

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: 44100,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      })

      chunks.current = []
      const recorder = new MediaRecorder(stream, {
        mimeType: MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
          ? "audio/webm;codecs=opus"
          : "audio/webm",
      })

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunks.current.push(e.data)
      }

      recorder.onstop = () => {
        const blob = new Blob(chunks.current, { type: "audio/webm" })
        setRecordedBlob(blob)
        setAudioUrl(URL.createObjectURL(blob))
        stream.getTracks().forEach((t) => t.stop())
      }

      recorder.start(250)
      mediaRecorder.current = recorder

      setRecording(true)
      setPaused(false)
      setElapsed(0)
      setAudioUrl(null)
      setRecordedBlob(null)

      timer.current = window.setInterval(() => {
        setElapsed((prev) => prev + 1)
      }, 1000)
    } catch (err: any) {
      alert("无法访问麦克风: " + err.message)
    }
  }

  const stopRecording = () => {
    mediaRecorder.current?.stop()
    setRecording(false)
    setPaused(false)
    if (timer.current) clearInterval(timer.current)
  }

  const handleSubmit = () => {
    if (recordedBlob && !loading) {
      onComplete(recordedBlob)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Record button area */}
      <div className="flex flex-col items-center gap-3 py-6">
        {!recording && !audioUrl && (
          <button
            onClick={startRecording}
            className="w-20 h-20 rounded-full bg-[var(--error)] hover:bg-red-600 flex items-center justify-center transition-all active:scale-95 cursor-pointer shadow-lg shadow-red-500/25"
          >
            <Mic className="w-8 h-8 text-white" />
          </button>
        )}

        {recording && (
          <div className="flex flex-col items-center gap-3">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-[var(--error)] animate-pulse" />
              <span className="text-[var(--error)] font-medium">录制中</span>
            </div>
            <p className="text-2xl font-mono text-[var(--text)]">
              {formatDuration(elapsed)}
            </p>
            <button
              onClick={stopRecording}
              className="w-14 h-14 rounded-full bg-[var(--surface-light)] hover:bg-[var(--text-muted)] flex items-center justify-center transition-all cursor-pointer"
            >
              <Square className="w-6 h-6 text-[var(--text)]" />
            </button>
          </div>
        )}

        {audioUrl && !recording && (
          <div className="flex flex-col items-center gap-3">
            <audio controls src={audioUrl} className="h-10 w-full max-w-xs" />
            <button
              onClick={startRecording}
              className="text-sm text-[var(--primary-light)] hover:underline cursor-pointer"
            >
              重新录制
            </button>
          </div>
        )}
      </div>

      {/* Submit */}
      <button
        onClick={handleSubmit}
        disabled={!recordedBlob || loading}
        className="w-full py-3 rounded-xl font-medium transition-all cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed bg-[var(--primary)] text-white hover:bg-[var(--primary-dark)] active:scale-[0.98]"
      >
        {loading ? (
          <span className="flex items-center justify-center gap-2">
            <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
            提交中...
          </span>
        ) : (
          <span className="flex items-center justify-center gap-2">
            <Music className="w-4 h-4" />
            将录音转为五线谱
          </span>
        )}
      </button>
    </div>
  )
}
