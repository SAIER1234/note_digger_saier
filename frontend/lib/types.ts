export type TranscriptionStatus =
  | "queued"
  | "processing"
  | "completed"
  | "failed"
  | "not_found"

export interface TranscriptionMeta {
  stage?: string
  duration?: number
  duration_seconds?: number
  sample_rate?: number
  channels?: number
  total_notes?: number
  tempo?: number
  pitch_range?: string
  num_tracks?: number
  has_drums?: boolean
  original_filename?: string
}

export interface TranscriptionResult {
  task_id: string
  celery_task_id?: string
  status: TranscriptionStatus
  filename?: string
  source_url?: string
  midi_url?: string
  musicxml_url?: string
  metadata?: TranscriptionMeta
  error?: string
  percent?: number
  stage?: string
  engine?: string
  chord_line?: string
  chords?: { start: number; end: number; chord: string; confidence: number }[]
  arranged?: boolean
  style?: string | null
}

export interface UploadResponse {
  task_id: string
  celery_task_id: string
  status: string
  filename?: string
  source_url?: string
}
