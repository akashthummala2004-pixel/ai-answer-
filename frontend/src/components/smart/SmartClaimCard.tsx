import { useState } from 'react';
import { BadgeCheck, ChevronDown, Quote, Undo2, UserCheck } from 'lucide-react';
import { ASSESSMENT_META, AssessmentBadge, Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { Alert } from '../ui/Feedback';
import { api, ApiError } from '../../lib/api';
import { formatDate } from '../../lib/format';
import { ASSESSMENTS, type Assessment, type SmartClaim, type SmartVerification } from '../../lib/types';

const BORDER: Record<Assessment, string> = {
  supported_by_evidence: 'border-l-green-500',
  contradicted_by_evidence: 'border-l-red-500',
  requires_human_review: 'border-l-amber-400',
  not_independently_verified: 'border-l-ink-300 dark:border-l-ink-600',
};

interface Props {
  verificationId: string;
  claim: SmartClaim;
  sourceLabels: Record<string, string>;
  onUpdated: (record: SmartVerification) => void;
  defaultOpen?: boolean;
}

export function effectiveAssessment(c: Pick<SmartClaim, 'assessment' | 'review'>): Assessment {
  return c.review ? c.review.verdict : c.assessment;
}

export function SmartClaimCard({ verificationId, claim, sourceLabels, onUpdated, defaultOpen = false }: Props) {
  const [open, setOpen] = useState(defaultOpen);
  const [verdict, setVerdict] = useState<Assessment>(claim.review?.verdict ?? claim.assessment);
  const [note, setNote] = useState(claim.review?.note ?? '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const shown = effectiveAssessment(claim);
  const url = `/api/verifications/${verificationId}/claims/${claim.id}/review`;

  async function save(method: 'PUT' | 'DELETE') {
    setBusy(true);
    setError(null);
    try {
      onUpdated(await api<SmartVerification>(url, { method, body: method === 'PUT' ? { verdict, note } : undefined }));
      if (method === 'DELETE') {
        setVerdict(claim.assessment);
        setNote('');
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not save the review.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={`rounded-xl border border-l-4 border-ink-200 bg-white dark:border-ink-800 dark:bg-ink-900 ${BORDER[shown]}`}>
      <button className="flex w-full items-start gap-3 p-4 text-left" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span className="mt-0.5 font-mono text-xs font-semibold text-ink-400">{claim.id}</span>
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-medium leading-relaxed text-ink-900 dark:text-white">{claim.text}</span>
          <span className="mt-2 flex flex-wrap items-center gap-2">
            <AssessmentBadge assessment={shown} />
            {claim.source && sourceLabels[claim.source] && <span className="text-xs text-ink-500">From {sourceLabels[claim.source]}</span>}
            {claim.review && <Badge tone="info" icon={<UserCheck className="h-3.5 w-3.5" />}>Human reviewed</Badge>}
          </span>
        </span>
        <ChevronDown className={`h-4 w-4 shrink-0 text-ink-400 transition ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="space-y-4 border-t border-ink-100 px-4 pb-4 pt-4 dark:border-ink-800">
          <p className="text-sm leading-relaxed text-ink-700 dark:text-ink-300">{claim.explanation}</p>

          {claim.evidence.length > 0 ? (
            <ul className="space-y-2">
              {claim.evidence.map((e, i) => (
                <li key={i} className="rounded-lg bg-ink-50 p-3 dark:bg-ink-800/60">
                  <div className="mb-1 flex flex-wrap items-center gap-2 text-xs">
                    <span className="font-medium text-ink-700 dark:text-ink-300">{e.label}</span>
                    <Badge tone="good" icon={<BadgeCheck className="h-3.5 w-3.5" />} title="The quoted text was found in the submitted material">
                      {e.match === 'near' ? 'Quote found (near-verbatim)' : 'Quote found in source'}
                    </Badge>
                  </div>
                  <p className="flex gap-2 text-sm italic text-ink-700 dark:text-ink-300"><Quote className="mt-0.5 h-3.5 w-3.5 shrink-0 text-ink-400" />{e.quote}</p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-ink-500">No supporting source available for this claim.</p>
          )}

          <div className="rounded-lg border border-dashed border-ink-300 p-3 dark:border-ink-700">
            <p className="text-xs font-semibold uppercase tracking-wide text-ink-500">Human review</p>
            {claim.review && (
              <p className="mt-1 text-xs text-ink-500">
                Reviewed {formatDate(claim.review.reviewed_at)}{claim.review.reviewer ? ` by ${claim.review.reviewer}` : ''} · AI assessment was “{ASSESSMENT_META[claim.assessment].label}”
              </p>
            )}
            <div className="mt-2 flex flex-wrap gap-1.5" role="radiogroup" aria-label="Reviewer assessment">
              {ASSESSMENTS.map((a) => {
                const { Icon, label } = ASSESSMENT_META[a];
                return (
                  <button
                    key={a}
                    type="button"
                    role="radio"
                    aria-checked={verdict === a}
                    onClick={() => setVerdict(a)}
                    className={`inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-medium transition ${
                      verdict === a ? 'border-brand-500 bg-brand-50 text-brand-800 dark:bg-brand-500/15 dark:text-brand-200' : 'border-ink-200 text-ink-600 hover:bg-ink-50 dark:border-ink-700 dark:text-ink-300 dark:hover:bg-ink-800'
                    }`}
                  >
                    <Icon className="h-3.5 w-3.5" />
                    {label}
                  </button>
                );
              })}
            </div>
            <textarea className="field mt-2 min-h-[64px]" maxLength={2000} placeholder="Reviewer note — what you checked and how…" value={note} onChange={(e) => setNote(e.target.value)} aria-label="Reviewer note" />
            {error && <div className="mt-2"><Alert tone="error">{error}</Alert></div>}
            <div className="mt-2 flex gap-2">
              <Button size="sm" loading={busy} onClick={() => save('PUT')} icon={<UserCheck className="h-3.5 w-3.5" />}>Save review</Button>
              {claim.review && <Button size="sm" variant="ghost" disabled={busy} onClick={() => save('DELETE')} icon={<Undo2 className="h-3.5 w-3.5" />}>Clear review</Button>}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
