import { useState } from 'react';
import { BadgeCheck, ChevronDown, Quote, ShieldAlert, UserCheck, Undo2 } from 'lucide-react';
import { Badge, VERDICT_META, VerdictBadge } from './ui/Badge';
import { Button } from './ui/Button';
import { Alert } from './ui/Feedback';
import { api, ApiError } from '../lib/api';
import { effectiveVerdict, formatDate, formatPercent } from '../lib/format';
import { VERDICTS, type Claim, type Verdict, type Verification } from '../lib/types';

const RING: Record<Verdict, string> = {
  supported: 'border-l-green-500',
  contradicted: 'border-l-red-500',
  uncertain: 'border-l-amber-400',
  unsupported: 'border-l-ink-300 dark:border-l-ink-600',
};

interface Props {
  verificationId: string;
  claim: Claim;
  onUpdated: (record: Verification) => void;
  defaultOpen?: boolean;
  highlighted?: boolean;
}

export function ClaimCard({ verificationId, claim, onUpdated, defaultOpen = false, highlighted }: Props) {
  const [open, setOpen] = useState(defaultOpen);
  const [verdict, setVerdict] = useState<Verdict>(claim.review?.verdict ?? claim.verdict);
  const [note, setNote] = useState(claim.review?.note ?? '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const shown = effectiveVerdict(claim);
  const reviewUrl = `/api/verifications/${verificationId}/claims/${claim.id}/review`;

  async function save(method: 'PUT' | 'DELETE') {
    setBusy(true);
    setError(null);
    try {
      const record = await api<Verification>(reviewUrl, { method, body: method === 'PUT' ? { verdict, note } : undefined });
      onUpdated(record);
      if (method === 'DELETE') {
        setVerdict(claim.verdict);
        setNote('');
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not save review.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div id={`claim-${claim.id}`} className={`rounded-xl border border-l-4 border-ink-200 bg-white transition dark:border-ink-800 dark:bg-ink-900 ${RING[shown]} ${highlighted ? 'ring-2 ring-brand-500/50' : ''}`}>
      <button className="flex w-full items-start gap-3 p-4 text-left" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span className="mt-0.5 font-mono text-xs font-semibold text-ink-400">{claim.id}</span>
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-medium text-ink-900 dark:text-white">{claim.text}</span>
          <span className="mt-2 flex flex-wrap items-center gap-2">
            <VerdictBadge verdict={shown} />
            <span className="text-xs tabular-nums text-ink-500">{formatPercent(claim.confidence)} confidence</span>
            {claim.review && <Badge tone="info" icon={<UserCheck className="h-3.5 w-3.5" />}>Human reviewed</Badge>}
            {claim.review && claim.review.verdict !== claim.verdict && (
              <span className="text-xs text-ink-500">system said <strong>{VERDICT_META[claim.verdict].label.toLowerCase()}</strong></span>
            )}
          </span>
        </span>
        <ChevronDown className={`h-4 w-4 shrink-0 text-ink-400 transition ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="space-y-4 border-t border-ink-100 px-4 pb-4 pt-4 dark:border-ink-800">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-ink-500">Explanation</p>
            <p className="mt-1 text-sm leading-relaxed text-ink-700 dark:text-ink-300">{claim.explanation}</p>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-ink-500">Cited evidence</p>
            {claim.evidence.length === 0 ? (
              <p className="mt-1 text-sm text-ink-500">No evidence passage was cited for this claim.</p>
            ) : (
              <ul className="mt-2 space-y-2">
                {claim.evidence.map((m, i) => (
                  <li key={i} className="rounded-lg bg-ink-50 p-3 dark:bg-ink-800/60">
                    <div className="mb-1 flex flex-wrap items-center gap-2 text-xs">
                      <span className="font-mono font-semibold text-ink-600 dark:text-ink-300">{m.evidence_id}</span>
                      <span className="text-ink-500">{m.evidence_title}</span>
                      {m.quote_verified && m.quote_match === 'near' ? (
                        <Badge tone="good" icon={<BadgeCheck className="h-3.5 w-3.5" />} title="The model's quote was near-verbatim; the exact evidence wording is shown">Quote verified (near-verbatim)</Badge>
                      ) : m.quote_verified ? (
                        <Badge tone="good" icon={<BadgeCheck className="h-3.5 w-3.5" />} title="Quote found verbatim in the evidence">Quote verified</Badge>
                      ) : (
                        <Badge tone="critical" icon={<ShieldAlert className="h-3.5 w-3.5" />} title="The model's quote does not appear in the evidence">Quote not found</Badge>
                      )}
                    </div>
                    <p className="flex gap-2 text-sm italic text-ink-700 dark:text-ink-300">
                      <Quote className="mt-0.5 h-3.5 w-3.5 shrink-0 text-ink-400" />
                      {m.quote}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="rounded-lg border border-dashed border-ink-300 p-3 dark:border-ink-700">
            <p className="text-xs font-semibold uppercase tracking-wide text-ink-500">Human review</p>
            {claim.review && (
              <p className="mt-1 text-xs text-ink-500">
                Last reviewed {formatDate(claim.review.reviewed_at)}{claim.review.reviewer ? ` by ${claim.review.reviewer}` : ''}
              </p>
            )}
            <div className="mt-2 flex flex-wrap gap-1.5" role="radiogroup" aria-label="Reviewer verdict">
              {VERDICTS.map((v) => {
                const { Icon, label } = VERDICT_META[v];
                return (
                  <button
                    key={v}
                    type="button"
                    role="radio"
                    aria-checked={verdict === v}
                    onClick={() => setVerdict(v)}
                    className={`inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-medium transition ${
                      verdict === v ? 'border-brand-500 bg-brand-50 text-brand-800 dark:bg-brand-500/15 dark:text-brand-200' : 'border-ink-200 text-ink-600 hover:bg-ink-50 dark:border-ink-700 dark:text-ink-300 dark:hover:bg-ink-800'
                    }`}
                  >
                    <Icon className="h-3.5 w-3.5" />
                    {label}
                  </button>
                );
              })}
            </div>
            <textarea className="field mt-2 min-h-[64px]" maxLength={2000} placeholder="Reviewer note (rationale, corrected fact, source)…" value={note} onChange={(e) => setNote(e.target.value)} aria-label="Reviewer note" />
            {error && <div className="mt-2"><Alert tone="error">{error}</Alert></div>}
            <div className="mt-2 flex gap-2">
              <Button size="sm" loading={busy} onClick={() => save('PUT')} icon={<UserCheck className="h-3.5 w-3.5" />}>Save review</Button>
              {claim.review && (
                <Button size="sm" variant="ghost" disabled={busy} onClick={() => save('DELETE')} icon={<Undo2 className="h-3.5 w-3.5" />}>Clear review</Button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
