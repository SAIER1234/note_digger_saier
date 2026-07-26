"use client"

import { useEffect, useRef, useState, useCallback } from "react"
import { Play, Pause, SkipBack, SkipForward, Download } from "lucide-react"
import { getMidiUrl } from "@/lib/api"

interface Props {
  taskId: string
}

/** Lightweight Web Audio MIDI synth — no external deps, plays in browser */
export function MidiPlayer({ taskId }: Props) {
  const [playing, setPlaying] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const audioCtxRef = useRef<AudioContext | null>(null)
  const midiDataRef = useRef<any>(null)
  const scheduledNodes = useRef<{ node: OscillatorNode; gain: GainNode; end: number }[]>([])
  const startTimeRef = useRef(0)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Load and parse MIDI
  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      setError(null)
      try {
        // Dynamically import midi parser (browser-only)
        const { parseMidi } = await import("midi-file")
        const res = await fetch(getMidiUrl(taskId))
        if (!res.ok) throw new Error("MIDI 加载失败")
        const buf = await res.arrayBuffer()
        const midi = parseMidi(new Uint8Array(buf))
        if (!cancelled) {
          midiDataRef.current = midi
          // Calculate total duration from MIDI ticks
          const ticksPerBeat = midi.header.ticksPerBeat || 480
          const tempo = 500000 // 120 BPM default (microseconds per beat)
          const secondsPerTick = tempo / 1_000_000 / ticksPerBeat
          let maxTicks = 0
          for (const track of midi.tracks) {
            let absTick = 0
            for (const event of track) {
              absTick += event.deltaTime || 0
              if (absTick > maxTicks) maxTicks = absTick
            }
          }
          const totalDuration = maxTicks * secondsPerTick
          setDuration(Math.max(totalDuration, 1))
          setLoading(false)
        }
      } catch (e: any) {
        if (!cancelled) {
          setError("MIDI 加载失败，请下载后用本地播放器播放")
          setLoading(false)
        }
      }
    }
    load()
    return () => { cancelled = true }
  }, [taskId])

  // Play MIDI with Web Audio oscillators
  const play = useCallback(() => {
    if (!midiDataRef.current) return
    stop()

    const ctx = new AudioContext()
    audioCtxRef.current = ctx
    const now = ctx.currentTime
    startTimeRef.current = now

    // Convert MIDI to oscillator schedule
    const tempo = 500000 // 120 BPM default (microseconds per quarter note)
    let tickPos = 0
    const ticksPerBeat = midiDataRef.current.header.ticksPerBeat || 480
    const secondsPerTick = (tempo / 1000000) / ticksPerBeat

    for (const track of midiDataRef.current.tracks) {
      let absTime = 0
      const activeNotes: Map<number, { osc: OscillatorNode; gain: GainNode }> = new Map()

      for (const event of track) {
        absTime += (event.deltaTime || 0) * secondsPerTick

        if (event.type === "noteOn" && (event as any).velocity > 0) {
          const pitch = (event as any).noteNumber
          const velocity = (event as any).velocity / 127
          const freq = 440 * Math.pow(2, (pitch - 69) / 12)

          const osc = ctx.createOscillator()
          const gain = ctx.createGain()
          osc.type = "triangle"
          osc.frequency.value = freq
          gain.gain.value = velocity * 0.3
          gain.gain.setValueAtTime(0, now + absTime)
          gain.gain.linearRampToValueAtTime(velocity * 0.3, now + absTime + 0.02)
          osc.connect(gain)
          gain.connect(ctx.destination)
          osc.start(now + absTime)
          activeNotes.set(pitch, { osc, gain })
          scheduledNodes.current.push({ node: osc, gain, end: now + absTime + 5 })
        }

        if ((event.type === "noteOff" || ((event as any).type === "noteOn" && (event as any).velocity === 0))) {
          const pitch = (event as any).noteNumber
          const note = activeNotes.get(pitch)
          if (note) {
            note.gain.gain.linearRampToValueAtTime(0, now + absTime + 0.05)
            note.osc.stop(now + absTime + 0.1)
            activeNotes.delete(pitch)
          }
        }
      }

      // Stop any remaining active notes
      for (const [, note] of activeNotes) {
        note.gain.gain.linearRampToValueAtTime(0, now + absTime + 1)
        note.osc.stop(now + absTime + 1.1)
      }
    }

    setPlaying(true)

    // Timer for currentTime display
    const totalDur = Math.max(duration, 10)
    timerRef.current = setInterval(() => {
      if (audioCtxRef.current) {
        const elapsed = audioCtxRef.current.currentTime - startTimeRef.current
        setCurrentTime(Math.min(elapsed, totalDur))
        if (elapsed >= totalDur + 2) {
          stop()
        }
      }
    }, 200)
  }, [duration])

  const stop = useCallback(() => {
    for (const { node, gain, end } of scheduledNodes.current) {
      try { gain.gain.value = 0; node.stop() } catch {}
    }
    scheduledNodes.current = []
    if (audioCtxRef.current) {
      audioCtxRef.current.close().catch(() => {})
      audioCtxRef.current = null
    }
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
    setPlaying(false)
    setCurrentTime(0)
  }, [])

  const togglePlay = () => {
    if (playing) stop()
    else play()
  }

  useEffect(() => { return stop }, [stop])

  const seek = (pct: number) => {
    stop()
    setCurrentTime(pct * duration)
  }

  return (
    <div className="bg-[var(--surface)] rounded-xl p-4 flex flex-col gap-3">
      {/* Progress bar */}
      <div className="flex items-center gap-3">
        <span className="text-xs text-[var(--text-muted)] font-mono w-12 text-right">
          {Math.floor(currentTime / 60)}:{(Math.floor(currentTime) % 60).toString().padStart(2, "0")}
        </span>
        <div className="flex-1 h-2 bg-[var(--surface-light)] rounded-full cursor-pointer group relative"
          onClick={(e) => {
            const rect = e.currentTarget.getBoundingClientRect()
            seek((e.clientX - rect.left) / rect.width)
          }}>
          <div className="h-full bg-[var(--primary)] rounded-full transition-all"
            style={{ width: `${duration ? (currentTime / duration) * 100 : 0}%` }} />
        </div>
        <span className="text-xs text-[var(--text-muted)] font-mono w-12">
          {Math.floor(duration / 60)}:{(Math.floor(duration) % 60).toString().padStart(2, "0")}
        </span>
      </div>

      {/* Controls */}
      <div className="flex items-center justify-center gap-3">
        <button onClick={() => seek(Math.max(0, currentTime / duration - 0.1))}
          className="p-2 rounded-lg text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-[var(--surface-light)] transition-all cursor-pointer">
          <SkipBack className="w-4 h-4" />
        </button>
        <button onClick={togglePlay} disabled={loading}
          className="p-3 rounded-full bg-[var(--primary)] text-white hover:bg-[var(--primary-dark)] transition-all cursor-pointer disabled:opacity-40">
          {loading ? <span className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin inline-block" />
            : playing ? <Pause className="w-5 h-5" />
            : <Play className="w-5 h-5 ml-0.5" />}
        </button>
        <button onClick={() => seek(Math.min(1, currentTime / duration + 0.1))}
          className="p-2 rounded-lg text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-[var(--surface-light)] transition-all cursor-pointer">
          <SkipForward className="w-4 h-4" />
        </button>
        <a href={getMidiUrl(taskId)} download
          className="p-2 rounded-lg text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-[var(--surface-light)] transition-all cursor-pointer ml-2"
          title="下载 MIDI">
          <Download className="w-4 h-4" />
        </a>
      </div>

      {error && <p className="text-xs text-[var(--error)] text-center">{error}</p>}
      {loading && !error && <p className="text-xs text-[var(--text-muted)] text-center">加载 MIDI...</p>}
    </div>
  )
}
