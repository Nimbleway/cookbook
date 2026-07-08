"use client";

import { useEffect, useRef, useState } from "react";
import { useReducedMotion } from "./use-reduced-motion";

const easeOutCubic = (t: number) => 1 - Math.pow(1 - t, 3);

// Animates a number from 0 → target with requestAnimationFrame + easeOutCubic.
// Re-runs whenever `target` changes (e.g. switching retailer/brand). Jumps
// straight to the final value under reduced-motion or when disabled.
export function useCountUp(
  target: number,
  { durationMs = 900, decimals = 0, enabled = true }: {
    durationMs?: number;
    decimals?: number;
    enabled?: boolean;
  } = {},
): number {
  const reduced = useReducedMotion();
  const [value, setValue] = useState(enabled && !reduced ? 0 : target);
  const frame = useRef<number | null>(null);

  useEffect(() => {
    // Jump straight to the target (scheduled, never a synchronous setState in
    // the effect body) when animation is off.
    if (!enabled || reduced) {
      frame.current = requestAnimationFrame(() => setValue(target));
      return () => {
        if (frame.current) cancelAnimationFrame(frame.current);
      };
    }
    const start = performance.now();
    const from = 0;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / durationMs);
      const eased = easeOutCubic(t);
      const next = from + (target - from) * eased;
      setValue(decimals ? Math.round(next * 10 ** decimals) / 10 ** decimals : Math.round(next));
      if (t < 1) frame.current = requestAnimationFrame(tick);
    };
    frame.current = requestAnimationFrame(tick);
    return () => {
      if (frame.current) cancelAnimationFrame(frame.current);
    };
  }, [target, durationMs, decimals, enabled, reduced]);

  return value;
}
