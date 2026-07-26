"use client"

import { useEffect, useRef, useState, useCallback } from "react"
import { getMidiUrl } from "@/lib/api"
import { formatDuration } from "@/lib/utils"

export function useMidiPlayer(taskId: string) {
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const [playing, setPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [volume, setVolume] = useState(0.8)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const audioUrl = getMidiUrl(taskId)  // Will try MP3 synthesis endpoint

  useEffect(() => {
    const audio = new Audio(audioUrl)
    audioRef.current = audio

    const onLoaded = () => {
      setDuration(audio.duration)
      setLoading(false)
    }
    const onTime = () => setCurrentTime(audio.currentTime)
    const onEnd = () => {
      setPlaying(false)
      setCurrentTime(0)
    }
    const onErr = () => {
      setError("音频加载失败")
      setLoading(false)
    }

    audio.addEventListener("loadedmetadata", onLoaded)
    audio.addEventListener("timeupdate", onTime)
    audio.addEventListener("ended", onEnd)
    audio.addEventListener("error", onErr)

    return () => {
      audio.removeEventListener("loadedmetadata", onLoaded)
      audio.removeEventListener("timeupdate", onTime)
      audio.removeEventListener("ended", onEnd)
      audio.removeEventListener("error", onErr)
      audio.pause()
      audio.src = ""
    }
  }, [audioUrl])

  const togglePlay = useCallback(() => {
    if (!audioRef.current) return
    if (playing) {
      audioRef.current.pause()
    } else {
      audioRef.current.play().catch(() => setError("播放失败"))
    }
    setPlaying(!playing)
  }, [playing])

  const seek = useCallback((time: number) => {
    if (audioRef.current) {
      audioRef.current.currentTime = time
      setCurrentTime(time)
    }
  }, [])

  const setAudioVolume = useCallback((v: number) => {
    setVolume(v)
    if (audioRef.current) audioRef.current.volume = v
  }, [])

  return {
    playing,
    currentTime,
    duration,
    volume,
    loading,
    error,
    togglePlay,
    seek,
    setVolume: setAudioVolume,
  }
}
