"use client";

import { useEffect, useRef, useState } from "react";
import { useReducedMotion } from "./use-reduced-motion";

// Returns [ref, inView] via IntersectionObserver. Used to trigger reveal/grow
// animations only once an element scrolls into view. Under reduced-motion it
// reports inView immediately so nothing stays hidden.
export function useInView<T extends HTMLElement = HTMLDivElement>(
  { once = true, rootMargin = "0px 0px -10% 0px", threshold = 0.15 }: {
    once?: boolean;
    rootMargin?: string;
    threshold?: number;
  } = {},
): [React.RefObject<T | null>, boolean] {
  const ref = useRef<T>(null);
  const reduced = useReducedMotion();
  // `seen` is only ever set from the IntersectionObserver callback (an event
  // callback, not the effect body) — so no setState-in-effect. Reduced-motion
  // is folded into the derived result.
  const [seen, setSeen] = useState(false);

  useEffect(() => {
    if (reduced) return;
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setSeen(true);
            if (once) obs.disconnect();
          } else if (!once) {
            setSeen(false);
          }
        }
      },
      { rootMargin, threshold },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [once, rootMargin, threshold, reduced]);

  return [ref, reduced || seen];
}
