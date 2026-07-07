"use client";

import { useEffect, useState } from "react";

type Section = { id: string; label: string };

// Sticky section tabs for the guided review. Tucks just under the site header
// (80px) on scroll; horizontal-scrolls on mobile. A fixed category label on the
// left keeps the "what am I looking at" anchor visible the whole way down —
// fixing the "header disconnects on scroll" problem. Scroll-spy highlights the
// active step; tabs smooth-scroll.
export function ResultsNav({
  sections,
  category,
  brand,
}: {
  sections: Section[];
  category?: string;
  brand?: string | null;
}) {
  const [active, setActive] = useState(sections[0]?.id ?? "");

  // Active = the topmost section in the upper viewport band. setState runs in
  // the observer callback (not the effect body).
  useEffect(() => {
    const els = sections
      .map((s) => document.getElementById(s.id))
      .filter((el): el is HTMLElement => el !== null);
    if (!els.length) return;
    const obs = new IntersectionObserver(
      (entries) => {
        const vis = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (vis[0]) setActive(vis[0].target.id);
      },
      { rootMargin: "-30% 0px -60% 0px", threshold: 0 },
    );
    els.forEach((el) => obs.observe(el));

    // The last section can't always scroll to the top band (page bottoms out
    // first), so the observer never marks it active. Force it when at bottom.
    const lastId = sections[sections.length - 1]?.id;
    const onScroll = () => {
      if (
        lastId &&
        window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4
      ) {
        setActive(lastId);
      }
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      obs.disconnect();
      window.removeEventListener("scroll", onScroll);
    };
  }, [sections]);

  const go = (id: string) =>
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });

  return (
    <nav
      aria-label="Report sections"
      className="sticky top-20 z-20 -mx-4 mb-6 border-b border-border bg-background/85 px-4 backdrop-blur"
    >
      <div className="flex items-center gap-3">
        {category && (
          <span className="hidden shrink-0 items-center gap-1.5 border-r border-border py-2.5 pr-3 text-xs font-bold capitalize tracking-tight sm:inline-flex">
            <span className="relative flex h-1.5 w-1.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-brand opacity-75" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-brand" />
            </span>
            {brand ? `${brand} · ${category}` : category}
          </span>
        )}
        <div className="flex flex-1 gap-1 overflow-x-auto [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {sections.map((s) => {
          const on = active === s.id;
          return (
            <button
              key={s.id}
              onClick={() => go(s.id)}
              aria-current={on}
              className={`relative shrink-0 whitespace-nowrap px-3 py-2.5 text-xs font-semibold tracking-tight transition ${
                on ? "text-foreground" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {s.label}
              {on && (
                <span className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-brand" />
              )}
            </button>
          );
          })}
        </div>
      </div>
    </nav>
  );
}
