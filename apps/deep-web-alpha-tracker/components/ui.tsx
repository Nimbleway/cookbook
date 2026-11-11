'use client';

import { useEffect, useRef, useState, type ReactNode } from 'react';
import type { Citation, Confidence, Evidence } from '@/lib/types';
import { hostOf } from '@/lib/trust';

export const CONF_COLOR: Record<Confidence, string> = {
  high: 'bg-up',
  medium: 'bg-warn',
  low: 'bg-down',
};

export function ConfDot({ c, label = false }: { c: Confidence; label?: boolean }) {
  return (
    <span className="inline-flex items-center gap-1.5" title={`${c} confidence`}>
      <span className={`inline-block h-2 w-2 rounded-full ${CONF_COLOR[c]}`} />
      {label && <span className="text-mute capitalize">{c}</span>}
    </span>
  );
}

/** Confidence plus a popover listing every page behind the row. */
export function Cite({ e }: { e: Evidence }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (ev: MouseEvent) => ref.current && !ref.current.contains(ev.target as Node) && setOpen(false);
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, [open]);
  return (
    <span ref={ref} className="relative inline-flex items-center gap-2">
      <ConfDot c={e.confidence} />
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="rounded border border-line px-1.5 py-px font-mono text-[11px] text-soft hover:border-accent hover:text-ink"
        aria-label={`${e.citations.length} citations`}
      >
        ↗{e.citations.length}
      </button>
      {open && <CitationList citations={e.citations} confidence={e.confidence} />}
    </span>
  );
}

function CitationList({ citations, confidence }: { citations: Citation[]; confidence: Confidence }) {
  return (
    <span className="absolute right-0 top-6 z-30 w-80 rounded-lg border border-line2 bg-panel2 p-2 text-left shadow-2xl shadow-black/50">
      <span className="mb-1.5 flex items-center justify-between px-1 text-[11px] uppercase tracking-wide text-mute">
        <span>Citations</span>
        <ConfDot c={confidence} label />
      </span>
      {citations.length === 0 && <span className="block px-1 py-1 text-mute">No citation returned</span>}
      {citations.map((c) => (
        <a key={c.url} href={c.url} target="_blank" rel="noreferrer" className="block rounded px-1.5 py-1 hover:bg-line">
          <span className="block truncate text-ink">{c.title}</span>
          <span className="flex justify-between text-[11px] text-mute">
            <span className="truncate">{hostOf(c.url)}</span>
            <span className={c.sourceType === 'primary' ? 'text-up' : ''}>{c.sourceType}</span>
          </span>
        </a>
      ))}
    </span>
  );
}

const TONES = {
  up: 'text-up bg-up/10 border-up/25',
  down: 'text-down bg-down/10 border-down/25',
  warn: 'text-warn bg-warn/10 border-warn/25',
  accent: 'text-accent bg-accent/10 border-accent/25',
  mute: 'text-soft bg-line/40 border-line2',
} as const;
export type Tone = keyof typeof TONES;

export function Pill({ tone = 'mute', children }: { tone?: Tone; children: ReactNode }) {
  return <span className={`inline-flex items-center whitespace-nowrap rounded border px-1.5 py-px text-[11px] font-medium ${TONES[tone]}`}>{children}</span>;
}

export function Arrow({ d }: { d: 'bullish' | 'bearish' | 'neutral' }) {
  return d === 'bullish' ? <span className="text-up">▲</span> : d === 'bearish' ? <span className="text-down">▼</span> : <span className="text-mute">●</span>;
}

export function Bar({ value, max, tone = 'accent', width = 'w-24' }: { value: number; max: number; tone?: 'accent' | 'up' | 'down' | 'warn'; width?: string }) {
  const pct = max > 0 ? Math.max(2, Math.min(100, (value / max) * 100)) : 0;
  const color = { accent: 'bg-accent', up: 'bg-up', down: 'bg-down', warn: 'bg-warn' }[tone];
  return (
    <span className={`inline-block h-1.5 ${width} overflow-hidden rounded-full bg-line`}>
      <span className={`block h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
    </span>
  );
}

export function MixBar({ mix }: { mix: Record<Confidence, number> }) {
  const total = mix.high + mix.medium + mix.low || 1;
  return (
    <span className="flex h-1.5 w-20 overflow-hidden rounded-full bg-line" title={`${mix.high} high · ${mix.medium} medium · ${mix.low} low`}>
      <span className="bg-up" style={{ width: `${(mix.high / total) * 100}%` }} />
      <span className="bg-warn" style={{ width: `${(mix.medium / total) * 100}%` }} />
      <span className="bg-down" style={{ width: `${(mix.low / total) * 100}%` }} />
    </span>
  );
}

export function Panel({ title, right, children, className = '' }: { title?: string; right?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-xl border border-line bg-panel ${className}`}>
      {title && (
        <header className="flex items-center justify-between border-b border-line px-4 py-2.5">
          <h3 className="text-[12px] font-semibold uppercase tracking-wide text-soft">{title}</h3>
          {right}
        </header>
      )}
      {children}
    </section>
  );
}

export function Stat({ label, value, sub }: { label: string; value: ReactNode; sub?: ReactNode }) {
  return (
    <div className="rounded-xl border border-line bg-panel px-4 py-3">
      <div className="text-[11px] uppercase tracking-wide text-mute">{label}</div>
      <div className="mt-1 font-mono text-xl font-semibold text-ink">{value}</div>
      {sub && <div className="mt-0.5 text-[11px] text-mute">{sub}</div>}
    </div>
  );
}

export interface Column<T> {
  key: string;
  label: string;
  render: (row: T) => ReactNode;
  sort?: (row: T) => number | string;
  align?: 'right' | 'left' | 'center';
  title?: string;
}

/** Sortable dense table. Click a header to sort; click again to flip. */
export function Table<T>({ rows, columns, rowKey, onRow, initialSort, empty = 'No rows at this confidence level' }: {
  rows: T[];
  columns: Column<T>[];
  rowKey: (row: T) => string;
  onRow?: (row: T) => void;
  initialSort?: { key: string; desc: boolean };
  empty?: string;
}) {
  const [sort, setSort] = useState(initialSort ?? null);
  const col = columns.find((c) => c.key === sort?.key);
  const sorted = col?.sort
    ? [...rows].sort((a, b) => {
        const x = col.sort!(a);
        const y = col.sort!(b);
        const cmp = typeof x === 'number' && typeof y === 'number' ? x - y : String(x).localeCompare(String(y));
        return sort!.desc ? -cmp : cmp;
      })
    : rows;
  return (
    <div className="scroll-thin overflow-x-auto">
      <table className="w-full border-collapse">
        <thead>
          <tr className="border-b border-line text-[11px] uppercase tracking-wide text-mute">
            {columns.map((c) => (
              <th
                key={c.key}
                title={c.title}
                onClick={() => c.sort && setSort((s) => ({ key: c.key, desc: s?.key === c.key ? !s.desc : true }))}
                className={`whitespace-nowrap px-3 py-2 font-medium ${c.align === 'right' ? 'text-right' : c.align === 'center' ? 'text-center' : 'text-left'} ${c.sort ? 'cursor-pointer select-none hover:text-ink' : ''}`}
              >
                {c.label}
                {sort?.key === c.key && <span className="ml-1 text-accent">{sort.desc ? '↓' : '↑'}</span>}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.length === 0 && (
            <tr>
              <td colSpan={columns.length} className="px-3 py-8 text-center text-mute">
                {empty}
              </td>
            </tr>
          )}
          {sorted.map((row) => (
            <tr key={rowKey(row)} onClick={onRow ? () => onRow(row) : undefined} className={`border-b border-line/60 ${onRow ? 'cursor-pointer hover:bg-panel2' : ''}`}>
              {columns.map((c) => (
                <td key={c.key} className={`whitespace-nowrap px-3 py-2 ${c.align === 'right' ? 'text-right' : c.align === 'center' ? 'text-center' : ''}`}>
                  {c.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Segmented<T extends string>({ value, options, onChange }: { value: T; options: { value: T; label: string }[]; onChange: (v: T) => void }) {
  return (
    <div className="inline-flex rounded-lg border border-line bg-panel p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          onClick={() => onChange(o.value)}
          className={`rounded-md px-2.5 py-1 text-[12px] ${value === o.value ? 'bg-panel2 text-ink shadow' : 'text-mute hover:text-ink'}`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export const label = (s: string) => s.replaceAll('_', ' ').replace(/^\w/, (m) => m.toUpperCase());
