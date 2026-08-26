'use client';

import React from 'react';
import ReactMarkdown, { type Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';

/**
 * Nimble returns the report as markdown with `[n]` callout markers. This
 * renders it, and turns each callout into a link to the source Nimble cited
 * for that claim. Prose styling lives in globals.css under `.prose`.
 */

export type TrustCitation = { url: string; title?: string | null };
export type TrustClaim = { callout?: number; confidence?: string; citations?: TrustCitation[] };
export type TrustSource = { url: string; type?: string; title?: string | null };
export type Trust = { confidence?: string; sources?: TrustSource[]; claims?: TrustClaim[] };

/**
 * Sources and citations come from the Nimble run, which sourced them from the
 * open web. Treat them as untrusted at the render boundary: only `http(s)`
 * reaches an `href`, so a `javascript:` or `data:` URL can never become a
 * clickable link. Returns undefined when the URL is unusable.
 */
export function safeExternalHref(url: string | null | undefined): string | undefined {
  if (!url) return undefined;
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    return undefined;
  }
  if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') return undefined;
  return parsed.toString();
}

/**
 * Rewrite `[1]` into a markdown link when Nimble supplied a usable citation for
 * that callout.
 *
 * The lookarounds make this idempotent: a marker already followed by `(` is an
 * existing link, and one preceded by `[` or followed by `]` is the inner half
 * of `[[1]](url)` from a previous pass. Neither is rewritten again.
 */
export function linkCitations(markdown: string, trust?: Trust): string {
  const urlByCallout = new Map<number, string>();
  for (const claim of trust?.claims ?? []) {
    const url = safeExternalHref(claim.citations?.[0]?.url);
    if (typeof claim.callout === 'number' && url) urlByCallout.set(claim.callout, url);
  }
  if (urlByCallout.size === 0) return markdown;

  return markdown.replace(/(?<!\[)\[(\d+)\](?!\]|\()/g, (marker, digits: string) => {
    const url = urlByCallout.get(Number(digits));
    // Parentheses would close the markdown link destination early, so encode
    // them rather than emitting a link that truncates mid-URL.
    return url ? `[${marker}](${url.replace(/\(/g, '%28').replace(/\)/g, '%29')})` : marker;
  });
}

/** True when a link's only child is a bare `[12]`, i.e. a citation callout. */
function isCallout(children: React.ReactNode): boolean {
  return typeof children === 'string' && /^\[\d+\]$/.test(children);
}

const components: Components = {
  // Every link opens in a new tab. Callouts get the compact pill treatment.
  // The report body is model-written, so validate here too rather than trusting
  // that linkCitations was the only thing that produced a link.
  a: ({ children, href }) => {
    const safeHref = safeExternalHref(href);
    if (!safeHref) return <>{children}</>;

    const callout = isCallout(children);
    return (
      <a
        href={safeHref}
        target="_blank"
        rel="noopener noreferrer"
        className={callout ? 'callout' : undefined}
        title={callout ? `Source Nimble cited for claim ${children}` : undefined}
      >
        {children}
      </a>
    );
  },
  // Wide tables scroll inside their own container rather than the page.
  table: ({ children }) => (
    <div className="table-scroll">
      <table>{children}</table>
    </div>
  ),
};

export function ReportMarkdown({ markdown, trust }: { markdown: string; trust?: Trust }) {
  return (
    <div className="prose">
      {/* Nimble's reports use GitHub Flavored Markdown. Without remark-gfm the
          comparison tables render as raw pipe characters. */}
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {linkCitations(markdown, trust)}
      </ReactMarkdown>
    </div>
  );
}
