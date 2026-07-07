"use client";

import { useInView } from "@/lib/use-in-view";

// Scroll-triggered reveal. Applies `animate-fade-up` (with an optional stagger
// delay) the first time the element enters the viewport. Reduced-motion users
// get the content immediately, fully visible (handled inside useInView).
export function Reveal({
  children,
  delayMs = 0,
  className,
  as: Tag = "div",
}: {
  children: React.ReactNode;
  delayMs?: number;
  className?: string;
  as?: "div" | "section";
}) {
  const [ref, inView] = useInView<HTMLDivElement>();
  return (
    <Tag
      ref={ref as React.RefObject<HTMLDivElement>}
      className={`${className ?? ""} ${inView ? "animate-fade-up" : "opacity-0"}`}
      style={inView ? { animationDelay: `${delayMs}ms` } : undefined}
    >
      {children}
    </Tag>
  );
}
