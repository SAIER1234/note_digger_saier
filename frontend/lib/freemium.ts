/** Freemium: localStorage-based free trial tracking (no server needed for MVP) */

const STORAGE_KEY = "note_digger_free_uses"
const MAX_FREE_USES = 3

export function getFreeUsesRemaining(): number {
  if (typeof window === "undefined") return 0
  const used = parseInt(localStorage.getItem(STORAGE_KEY) || "0", 10)
  return Math.max(0, MAX_FREE_USES - used)
}

export function useFreeCredit(): boolean {
  if (typeof window === "undefined") return false
  const remaining = getFreeUsesRemaining()
  if (remaining <= 0) return false
  const used = parseInt(localStorage.getItem(STORAGE_KEY) || "0", 10)
  localStorage.setItem(STORAGE_KEY, String(used + 1))
  return true
}

export function isFreeUser(): boolean {
  return getFreeUsesRemaining() > 0
}

export function getTierLabel(): string {
  const remaining = getFreeUsesRemaining()
  if (remaining > 0) return `免费试用 · 剩余 ${remaining} 次`
  return "基础版 · Basic Pitch"
}
