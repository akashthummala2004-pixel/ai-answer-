import type { Claim, Verdict } from './types';

export function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

export function formatPercent(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return `${(value * 100).toFixed(digits)}%`;
}

export function formatScore(value: number | null | undefined): string {
  return value === null || value === undefined ? '—' : value.toFixed(1);
}

export function effectiveVerdict(claim: Pick<Claim, 'verdict' | 'review'>): Verdict {
  return claim.review ? claim.review.verdict : claim.verdict;
}

export function scoreTone(score: number | null | undefined): 'good' | 'warning' | 'critical' | 'neutral' {
  if (score === null || score === undefined) return 'neutral';
  if (score >= 75) return 'good';
  if (score >= 50) return 'warning';
  return 'critical';
}

/** Splits `text` into segments, tagging the ranges where each claim's text occurs verbatim. */
export function highlightClaims(text: string, claims: Pick<Claim, 'id' | 'text'>[]) {
  const ranges: { start: number; end: number; id: string }[] = [];
  const lower = text.toLowerCase();
  for (const claim of claims) {
    const needle = claim.text.trim().toLowerCase();
    if (!needle) continue;
    const start = lower.indexOf(needle);
    if (start === -1) continue;
    const end = start + needle.length;
    if (ranges.some((r) => start < r.end && end > r.start)) continue;
    ranges.push({ start, end, id: claim.id });
  }
  ranges.sort((a, b) => a.start - b.start);
  const segments: { text: string; claimId: string | null }[] = [];
  let cursor = 0;
  for (const r of ranges) {
    if (r.start > cursor) segments.push({ text: text.slice(cursor, r.start), claimId: null });
    segments.push({ text: text.slice(r.start, r.end), claimId: r.id });
    cursor = r.end;
  }
  if (cursor < text.length) segments.push({ text: text.slice(cursor), claimId: null });
  return segments;
}
