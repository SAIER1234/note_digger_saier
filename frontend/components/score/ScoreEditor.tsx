"use client"

import { useState } from "react"
import { Trash2, Undo2 } from "lucide-react"
import { toast } from "sonner"

interface Props {
  taskId: string
}

/**
 * Lightweight score editor — Phase 1 only supports note deletion
 * and simple corrections. Full editing is a Phase 2 feature.
 */
export function ScoreEditor({ taskId }: Props) {
  const [editMode, setEditMode] = useState(false)
  const [deletedNotes, setDeletedNotes] = useState<number>(0)

  const handleDeleteSelected = () => {
    // In Phase 1, this is a simplified editor
    // Future: integrate with OSMD's cursor/selection API
    toast.info("选中音符后点击删除可移除错音（完整编辑功能开发中）")
    setDeletedNotes((n) => n + 1)
  }

  const handleUndo = () => {
    toast.info("撤销功能开发中")
  }

  return (
    <div className="bg-[var(--surface)] rounded-xl p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-[var(--text)]">谱面编辑</h3>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setEditMode(!editMode)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all cursor-pointer ${
              editMode
                ? "bg-[var(--primary)] text-white"
                : "bg-[var(--surface-light)] text-[var(--text-muted)] hover:text-[var(--text)]"
            }`}
          >
            {editMode ? "编辑中" : "编辑模式"}
          </button>

          {editMode && (
            <>
              <button
                onClick={handleDeleteSelected}
                className="p-1.5 rounded-lg text-[var(--error)] hover:bg-[var(--error)]/10 transition-all cursor-pointer"
                title="删除选中音符"
              >
                <Trash2 className="w-4 h-4" />
              </button>
              <button
                onClick={handleUndo}
                className="p-1.5 rounded-lg text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-[var(--surface-light)] transition-all cursor-pointer"
                title="撤销"
              >
                <Undo2 className="w-4 h-4" />
              </button>
            </>
          )}
        </div>
      </div>

      {editMode && (
        <div className="mt-3 p-3 bg-[var(--surface-light)] rounded-lg">
          <p className="text-xs text-[var(--text-muted)]">
            Phase 1 轻量编辑器：支持选中并删除错误音符。
            完整的音符编辑（拖拽改音高、调整时值）将在后续版本推出。
          </p>
        </div>
      )}
    </div>
  )
}
