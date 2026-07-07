/* eslint-disable @next/next/no-img-element */
"use client";

import { useMemo, useState } from "react";
import { brandColor, brandLogoSources, logoSourcesForDomain } from "@/lib/mock-data";
import { RETAILER_META } from "@/lib/retailers";
import type { RetailerId } from "@/lib/types";

const DIMS = {
  sm: "h-11 w-11",
  md: "h-16 w-16",
  lg: "h-20 w-20",
  xl: "h-28 w-28",
} as const;

// Renders the best available visual for a product, in order:
//   1. live product photo (imageUrl from Nimble), 2. real brand logo,
//   3. branded gradient tile with initials.
// Each <img> falls through to the next source on error, so it never breaks.
export function ProductImage({
  brand,
  imageUrl,
  title,
  size = "md",
  href,
}: {
  brand: string;
  imageUrl?: string;
  title?: string;
  size?: "sm" | "md" | "lg" | "xl";
  href?: string;
}) {
  // Build the source chain once.
  const sources = useMemo(() => {
    const list: { src: string; kind: "photo" | "logo" }[] = [];
    if (imageUrl && imageUrl !== "#") list.push({ src: imageUrl, kind: "photo" });
    for (const s of brandLogoSources(brand)) list.push({ src: s, kind: "logo" });
    return list;
  }, [imageUrl, brand]);

  const [idx, setIdx] = useState(0);
  const [loadedSrc, setLoadedSrc] = useState<string | null>(null);
  const current = sources[idx];
  const dims = DIMS[size];

  // All sources exhausted (or none) → branded gradient tile.
  if (!current) {
    return <LiveLink href={href}><GradientTile brand={brand} title={title} size={size} /></LiveLink>;
  }

  const isPhoto = current.kind === "photo";
  const ready = loadedSrc === current.src;
  return (
    <LiveLink href={href}>
      <div
        className={`${dims} relative shrink-0 overflow-hidden rounded-xl ring-1 ring-black/[0.06] ${
          ready ? "" : "skeleton"
        }`}
        style={isPhoto || !ready ? undefined : { background: "white" }}
        title={title ?? brand}
      >
        <img
          src={current.src}
          alt={title ?? brand}
          loading="lazy"
          onLoad={() => setLoadedSrc(current.src)}
          onError={() => setIdx((i) => i + 1)}
          className={`h-full w-full transition-opacity duration-300 ${
            ready ? "opacity-100" : "opacity-0"
          } ${isPhoto ? "object-cover" : "object-contain p-1.5"}`}
        />
      </div>
    </LiveLink>
  );
}

// Wraps a product visual in a link to the live retailer PDP when a real URL
// exists (mock rows use "#", which stays unlinked). The live page is the proof.
function LiveLink({ href, children }: { href?: string; children: React.ReactNode }) {
  if (!href || href === "#") return <>{children}</>;
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="group/live relative block shrink-0"
      title="View live on the retailer ↗"
    >
      {children}
    </a>
  );
}

function GradientTile({
  brand,
  title,
  size = "md",
}: {
  brand: string;
  title?: string;
  size?: "sm" | "md" | "lg" | "xl";
}) {
  const color = brandColor(brand);
  const dims = DIMS[size];
  const initials = brand
    .replace(/[^a-zA-Z0-9 ]/g, "")
    .split(" ")
    .slice(0, 2)
    .map((w) => w[0])
    .join("")
    .toUpperCase();
  return (
    <div
      className={`${dims} relative shrink-0 overflow-hidden rounded-xl ring-1 ring-black/[0.06]`}
      style={{
        background: `linear-gradient(135deg, ${color} 0%, color-mix(in oklab, ${color} 55%, white) 100%)`,
      }}
      aria-label={title ?? brand}
      title={title ?? brand}
    >
      <div className="absolute inset-0 opacity-20 [background:radial-gradient(circle_at_30%_20%,white,transparent_55%)]" />
      <div className="absolute inset-0 flex items-center justify-center">
        <span
          className="font-semibold tracking-tight text-white drop-shadow-sm"
          style={{ fontSize: size === "sm" ? 13 : size === "xl" ? 30 : size === "lg" ? 22 : 17 }}
        >
          {initials}
        </span>
      </div>
    </div>
  );
}

// Back-compat alias — existing call sites import { ProductTile }.
export const ProductTile = ProductImage;

// Real retailer favicon (Amazon/Walmart/Target) in a white chip, with a
// colored-dot fallback so a missed favicon never shows a broken image.
export function RetailerLogo({
  retailer,
  className,
}: {
  retailer: RetailerId;
  className?: string;
}) {
  const meta = RETAILER_META[retailer];
  // Local bundled icon FIRST (bulletproof, works offline at the booth), then the
  // favicon CDNs, then the colored-dot fallback — so it's never just a dot.
  const sources = useMemo(
    () => [`/retailers/${retailer}.png`, ...logoSourcesForDomain(meta.domain)],
    [retailer, meta.domain],
  );
  const [idx, setIdx] = useState(0);
  const [ready, setReady] = useState(false);
  const src = sources[idx];
  return (
    <span
      className={`relative inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full bg-white ring-1 ring-black/10 ${className ?? "h-7 w-7"}`}
    >
      {(!src || !ready) && (
        <span
          aria-hidden
          className="h-2 w-2 rounded-full"
          style={{ background: meta.color }}
        />
      )}
      {src && (
        <img
          src={src}
          alt={meta.label}
          loading="lazy"
          referrerPolicy="no-referrer"
          onLoad={() => setReady(true)}
          onError={() => {
            setReady(false);
            setIdx((i) => i + 1);
          }}
          className={`absolute inset-0 h-full w-full object-contain p-1 transition-opacity duration-200 ${
            ready ? "opacity-100" : "opacity-0"
          }`}
        />
      )}
    </span>
  );
}

// Fills its parent container (object-contain) with the best available image —
// real product photo → brand logo → brand wordmark. Use inside a sized box.
export function ProductPhoto({
  brand,
  imageUrl,
  title,
  href,
}: {
  brand: string;
  imageUrl?: string;
  title?: string;
  href?: string;
}) {
  const sources = useMemo(() => {
    const list: string[] = [];
    if (imageUrl && imageUrl !== "#") list.push(imageUrl);
    for (const s of brandLogoSources(brand)) list.push(s);
    return list;
  }, [imageUrl, brand]);
  const [idx, setIdx] = useState(0);
  const [ready, setReady] = useState(false);
  const src = sources[idx];
  const linkable = href && href !== "#";
  const Tag = linkable ? "a" : "div";
  const linkProps = linkable
    ? { href, target: "_blank" as const, rel: "noopener noreferrer", title: "View live on the retailer ↗" }
    : {};

  if (!src) {
    return (
      <Tag
        {...linkProps}
        className="flex h-full w-full items-center justify-center p-2 text-center text-sm font-semibold text-neutral-500"
      >
        {brand}
      </Tag>
    );
  }
  return (
    <Tag {...linkProps} className="block h-full w-full">
      <img
        src={src}
        alt={title ?? brand}
        loading="lazy"
        onLoad={() => setReady(true)}
        onError={() => {
          setReady(false);
          setIdx((i) => i + 1);
        }}
        className={`h-full w-full object-contain p-3 transition-opacity duration-300 ${
          ready ? "opacity-100" : "opacity-0"
        }`}
      />
    </Tag>
  );
}

// A clean colored monogram — the always-renders fallback so a broken <img>
// never appears (booth wifi / deprecated logo CDNs can't break it).
function Monogram({ brand }: { brand: string }) {
  const color = brandColor(brand);
  const initial = (brand.replace(/[^a-zA-Z0-9]/g, "")[0] ?? "?").toUpperCase();
  return (
    <span
      aria-hidden
      className="flex h-full w-full items-center justify-center rounded-full text-[0.62em] font-bold leading-none text-white"
      style={{
        background: `linear-gradient(135deg, ${color}, color-mix(in oklab, ${color} 60%, white))`,
      }}
    >
      {initial}
    </span>
  );
}

// Brand logo for chips / strips / clusters. Shows the real favicon when it
// loads, a monogram otherwise — never a broken image. `className` sizes the box.
export function BrandLogo({
  brand,
  className,
}: {
  brand: string;
  className?: string;
}) {
  const sources = useMemo(() => brandLogoSources(brand), [brand]);
  const [idx, setIdx] = useState(0);
  const [ready, setReady] = useState(false);
  const src = sources[idx];
  return (
    <span className={`relative inline-flex shrink-0 overflow-hidden ${className ?? "h-7 w-7"}`}>
      {(!src || !ready) && <Monogram brand={brand} />}
      {src && (
        <img
          src={src}
          alt={brand}
          loading="lazy"
          referrerPolicy="no-referrer"
          onLoad={() => setReady(true)}
          onError={() => {
            setReady(false);
            setIdx((i) => i + 1);
          }}
          className={`absolute inset-0 h-full w-full object-contain transition-opacity duration-200 ${
            ready ? "opacity-100" : "opacity-0"
          }`}
        />
      )}
    </span>
  );
}
