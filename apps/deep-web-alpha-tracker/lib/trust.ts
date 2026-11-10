import type { Citation, Confidence, Evidence } from './types';

interface RawCitation {
  url?: string;
  title?: string;
  source_type?: string;
}

export interface RawClaim {
  path: string;
  confidence?: string;
  citations?: RawCitation[];
}

const RANK: Record<Confidence, number> = { low: 0, medium: 1, high: 2 };

function asConfidence(value: string | undefined): Confidence {
  return value === 'high' || value === 'medium' ? value : 'low';
}

/**
 * Evidence for one output row: the median confidence of the trust claims under the row's JSON path,
 * and the distinct pages they cite. A row with no claims is graded low.
 */
export function evidenceFor(claims: RawClaim[], rowPath: string, fallbackUrl?: string | null): Evidence {
  const under = claims.filter((c) => c.path === rowPath || c.path.startsWith(`${rowPath}.`) || c.path.startsWith(`${rowPath}[`));
  const grades = under.map((c) => asConfidence(c.confidence)).sort((a, b) => RANK[a] - RANK[b]);
  const confidence: Confidence = grades.length ? grades[Math.floor((grades.length - 1) / 2)] : 'low';
  const seen = new Set<string>();
  const citations: Citation[] = [];
  for (const claim of under) {
    for (const raw of claim.citations ?? []) {
      if (!raw.url || seen.has(raw.url)) continue;
      seen.add(raw.url);
      citations.push({
        url: raw.url,
        title: raw.title && raw.title !== raw.url ? raw.title : hostOf(raw.url),
        sourceType: raw.source_type === 'primary' || raw.source_type === 'secondary' || raw.source_type === 'tertiary' ? raw.source_type : 'unknown',
      });
    }
  }
  if (!citations.length && fallbackUrl?.startsWith('http')) {
    citations.push({ url: fallbackUrl, title: hostOf(fallbackUrl), sourceType: 'unknown' });
  }
  return { confidence, citations };
}

export function hostOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url;
  }
}
