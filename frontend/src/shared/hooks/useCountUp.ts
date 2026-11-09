/**
 * Número que "cuenta" desde 0 hasta el valor (animación de entrada de KPIs).
 *
 * - requestAnimationFrame + easing ease-out (rápido al inicio, suave al final).
 * - prefers-reduced-motion: devuelve el valor final directamente (sin animar).
 * - Si el valor cambia (polling), cuenta desde el valor anterior, no desde 0.
 */
import { useEffect, useRef, useState } from 'react'

const DEFAULT_DURATION_MS = 800

function prefersReducedMotion(): boolean {
  return typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches === true
}

const easeOutCubic = (t: number) => 1 - (1 - t) ** 3

export function useCountUp(target: number, durationMs = DEFAULT_DURATION_MS): number {
  const [reduced] = useState(prefersReducedMotion)
  const [value, setValue] = useState(0)
  const fromRef = useRef(0)

  useEffect(() => {
    if (reduced) return
    const from = fromRef.current
    const started = performance.now()
    let frame = 0
    const tick = (now: number) => {
      const progress = Math.min(1, (now - started) / durationMs)
      setValue(Math.round(from + (target - from) * easeOutCubic(progress))) // dentro del callback de rAF
      if (progress < 1) frame = requestAnimationFrame(tick)
      else fromRef.current = target
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [target, durationMs, reduced])

  return reduced ? target : value
}
