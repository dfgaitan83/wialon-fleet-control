/**
 * Reproducción (playback) del recorrido: índice actual, play/pausa y velocidad.
 * Avanza por PUNTOS (no por tiempo real): con 2000 puntos y x1 el recorrido dura
 * ~3 min; x4/x16 aceleran. Al llegar al final se pausa solo.
 */
import { useCallback, useEffect, useState } from 'react'

export const PLAYBACK_TICK_MS = 100
export const PLAYBACK_SPEEDS = [1, 4, 16] as const
export type PlaybackSpeed = (typeof PLAYBACK_SPEEDS)[number]

export function usePlayback(length: number) {
  const [index, setIndex] = useState(0)
  const [isPlaying, setPlaying] = useState(false)
  const [speed, setSpeed] = useState<PlaybackSpeed>(4)
  const [prevLength, setPrevLength] = useState(length)

  // Recorrido nuevo -> vuelve al inicio en pausa (ajuste durante el render, sin efecto extra).
  if (length !== prevLength) {
    setPrevLength(length)
    setIndex(0)
    setPlaying(false)
  }

  useEffect(() => {
    if (!isPlaying) return
    const timer = window.setInterval(() => {
      setIndex((current) => Math.min(current + speed, length - 1))
    }, PLAYBACK_TICK_MS)
    return () => window.clearInterval(timer)
  }, [isPlaying, speed, length])

  // Al llegar al final se detiene solo.
  if (isPlaying && index >= length - 1) setPlaying(false)

  const toggle = useCallback(() => {
    if (length < 2) return
    if (!isPlaying && index >= length - 1) setIndex(0) // al final: reinicia
    setPlaying(!isPlaying)
  }, [length, isPlaying, index])

  const seek = useCallback((value: number) => setIndex(Math.max(0, Math.min(value, length - 1))), [length])

  return { index, isPlaying, speed, setSpeed, toggle, seek }
}
