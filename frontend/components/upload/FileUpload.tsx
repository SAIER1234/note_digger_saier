"use client"

import { useCallback, useState } from "react"
import { Upload, Music, FileAudio } from "lucide-react"
import { formatFileSize } from "@/lib/utils"

interface Props {
  onFile: (file: File) => void
  loading: boolean
}

const ACCEPTED_TYPES = [
  "audio/wav",
  "audio/mpeg",
  "audio/mp3",
  "audio/flac",
  "audio/x-flac",
  "audio/mp4",
  "audio/x-m4a",
  "audio/ogg",
]

export function FileUpload({ onFile, loading }: Props) {
  const [dragOver, setDragOver] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)

  const isValidFile = (file: File) => {
    const ext = file.name.split(".").pop()?.toLowerCase()
    const validExts = ["wav", "mp3", "flac", "m4a", "ogg", "aac", "wma"]
    return validExts.includes(ext || "") || ACCEPTED_TYPES.includes(file.type)
  }

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setDragOver(false)
      const file = e.dataTransfer.files[0]
      if (file && isValidFile(file)) {
        setSelectedFile(file)
      }
    },
    []
  )

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file && isValidFile(file)) {
      setSelectedFile(file)
    }
  }

  const handleSubmit = () => {
    if (selectedFile && !loading) {
      onFile(selectedFile)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all ${
          dragOver
            ? "border-[var(--primary)] bg-[var(--primary)]/10 scale-[1.02]"
            : selectedFile
            ? "border-[var(--success)] bg-[var(--success)]/5"
            : "border-[var(--surface-light)] hover:border-[var(--primary-light)] hover:bg-[var(--surface-light)]/50"
        }`}
        onClick={() => document.getElementById("file-input")?.click()}
      >
        <input
          id="file-input"
          type="file"
          accept="audio/*"
          className="hidden"
          onChange={handleChange}
        />

        {selectedFile ? (
          <div className="flex flex-col items-center gap-2">
            <FileAudio className="w-10 h-10 text-[var(--success)]" />
            <p className="font-medium text-[var(--text)]">{selectedFile.name}</p>
            <p className="text-sm text-[var(--text-muted)]">
              {formatFileSize(selectedFile.size)}
            </p>
            <p className="text-xs text-[var(--text-muted)]">点击重新选择</p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3">
            <Upload className="w-10 h-10 text-[var(--text-muted)]" />
            <div>
              <p className="font-medium text-[var(--text)]">拖拽音频文件到此处</p>
              <p className="text-sm text-[var(--text-muted)] mt-1">
                或点击选择文件 · MP3 / WAV / FLAC / M4A
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Submit button */}
      <button
        onClick={handleSubmit}
        disabled={!selectedFile || loading}
        className="w-full py-3 rounded-xl font-medium transition-all cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed bg-[var(--primary)] text-white hover:bg-[var(--primary-dark)] active:scale-[0.98]"
      >
        {loading ? (
          <span className="flex items-center justify-center gap-2">
            <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
            处理中...
          </span>
        ) : (
          <span className="flex items-center justify-center gap-2">
            <Music className="w-4 h-4" />
            开始扒谱
          </span>
        )}
      </button>
    </div>
  )
}
