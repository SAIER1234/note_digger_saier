"use client"

import { useState, useEffect, useCallback, useRef } from "react"
import type { TranscriptionResult, TranscriptionStatus } from "@/lib/types"
import { getTaskStatus } from "@/lib/api"

interface UseTranscriptionOptions {
  taskId: string
  pollInterval?: number // ms
}

export function useTranscription({ taskId, pollInterval = 2000 }: UseTranscriptionOptions) {
  const [result, setResult] = useState<TranscriptionResult | null>(null)
  const [status, setStatus] = useState<TranscriptionStatus>("queued")
  const [error, setError] = useState<string | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const poll = useCallback(async () => {
    try {
      const data = await getTaskStatus(taskId)
      setResult(data)
      setStatus(data.status)

      if (data.status === "completed" || data.status === "failed") {
        if (timerRef.current) {
          clearInterval(timerRef.current)
          timerRef.current = null
        }
        if (data.status === "failed") {
          setError(data.error || "转录失败")
        }
      }
    } catch (err: any) {
      setError(err.message)
    }
  }, [taskId])

  useEffect(() => {
    // Initial poll
    poll()

    // Start polling
    timerRef.current = setInterval(poll, pollInterval)

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current)
      }
    }
  }, [poll, pollInterval])

  const stageLabel = result?.stage || "处理中..."
  const percent = result?.percent ?? 0

  return {
    result,
    status,
    error,
    stageLabel,
    percent,
    isLoading: status === "queued" || status === "processing" || status === "not_found",
    isCompleted: status === "completed",
    isFailed: status === "failed",
  }
}
