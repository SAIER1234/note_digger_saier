import type { TranscriptionResult, UploadResponse } from "./types"
import { getToken } from "./auth"

// Production: use relative paths (Nginx handles routing)
// Development: set NEXT_PUBLIC_API_URL=http://localhost:8002 in .env.local
const DEFAULT_API_BASE = process.env.NEXT_PUBLIC_API_URL || ""

export function getApiBase(): string {
  // Allow runtime override via URL param ?api=http://...
  if (typeof window !== "undefined") {
    const params = new URLSearchParams(window.location.search)
    const override = params.get("api")
    if (override) return override
  }
  return DEFAULT_API_BASE
}
const API_PREFIX = "/api/v1"

async function request<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${getApiBase()}${endpoint}`, {
    ...options,
    headers: {
      ...(options?.headers || {}),
    },
  })

  if (!res.ok) {
    const body = await res.text()
    throw new Error(body || `HTTP ${res.status}`)
  }

  return res.json()
}

export async function uploadFile(
  file: File,
  model: string = "auto",
  arrange: boolean = false,
  style: string = "broken",
): Promise<UploadResponse> {
  const form = new FormData()
  form.append("file", file)
  form.append("model", model)
  // Include auth token if logged in
  const token = getToken()
  if (token) form.append("token", token)
  if (arrange) {
    form.append("arrange", "true")
    form.append("style", style)
    form.append("difficulty", "medium")
  }

  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 30_000)

  try {
    const res = await fetch(`${getApiBase()}${API_PREFIX}/transcribe/file`, {
      method: "POST",
      body: form,
      signal: controller.signal,
    })

    if (!res.ok) {
      const body = await res.text()
      throw new Error(body || "上传失败")
    }

    return res.json()
  } catch (err: any) {
    if (err.name === "AbortError") throw new Error("上传超时，请检查网络连接")
    if (err.message?.includes("Failed to fetch") || err.message?.includes("NetworkError"))
      throw new Error("无法连接到后端服务，请确认后端已启动")
    throw err
  } finally {
    clearTimeout(timeout)
  }
}

export async function transcribeUrl(
  url: string,
  model: string = "auto",
  arrange: boolean = false,
  style: string = "broken",
): Promise<UploadResponse> {
  const form = new FormData()
  form.append("url", url)
  form.append("model", model)
  if (arrange) {
    form.append("arrange", "true")
    form.append("style", style)
    form.append("difficulty", "medium")
  }

  const res = await fetch(`${getApiBase()}${API_PREFIX}/transcribe/url`, {
    method: "POST",
    body: form,
  })

  if (!res.ok) {
    const body = await res.text()
    throw new Error(body || "提交失败")
  }

  return res.json()
}

export async function uploadRecording(
  blob: Blob,
  model: string = "auto",
  arrange: boolean = false,
  style: string = "broken",
): Promise<UploadResponse> {
  const form = new FormData()
  form.append("file", blob, "recording.wav")
  form.append("model", model)
  if (arrange) {
    form.append("arrange", "true")
    form.append("style", style)
    form.append("difficulty", "medium")
  }

  const res = await fetch(`${getApiBase()}${API_PREFIX}/transcribe/record`, {
    method: "POST",
    body: form,
  })

  if (!res.ok) {
    const body = await res.text()
    throw new Error(body || "上传录音失败")
  }

  return res.json()
}

export async function getTaskStatus(
  taskId: string
): Promise<TranscriptionResult> {
  return request(`${API_PREFIX}/transcribe/${taskId}`)
}

export function getMidiUrl(taskId: string): string {
  return `${getApiBase()}${API_PREFIX}/export/${taskId}/midi`
}

export function getMusicXmlUrl(taskId: string): string {
  return `${getApiBase()}${API_PREFIX}/export/${taskId}/musicxml_text`
}

export function getPdfUrl(taskId: string): string {
  return `${getApiBase()}${API_PREFIX}/export/${taskId}/pdf`
}

export function getAudioUrl(taskId: string): string {
  return `${getApiBase()}${API_PREFIX}/export/${taskId}/audio`
}
