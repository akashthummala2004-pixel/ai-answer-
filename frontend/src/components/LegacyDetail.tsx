import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowLeft, ExternalLink, FileDown, FileJson, Trash2 } from 'lucide-react';
import { ClaimCard } from './ClaimCard';
import { EngineBadge, VERDICT_META } from './ui/Badge';
import { Button } from './ui/Button';
import { Card, CardBody, CardHeader, PageHeader } from './ui/Card';
import { Alert } from './ui/Feedback';
import { api, ApiError, downloadFile } from '../lib/api';
import { effectiveVerdict, formatDate, formatScore, highlightClaims, scoreTone } from '../lib/format';
import { useChartColors } from '../lib/theme';
import { VERDICTS, type Verdict, type Verification } from '../lib/types';

const HIGHLIGHT: Record<Verdict, string> = {
  supported: 'bg-green-100 decoration-green-600 dark:bg-green-500/15',
  contradicted: 'bg-red-100 decoration-red-600 dark:bg-red-500/20',
  uncertain: 'bg-amber-100 decoration-amber-500 dark:bg-amber-500/15',
  unsupported: 'bg-ink-100 decoration-ink-400 dark:bg-ink-700/60',
};

function ScoreRing({ score }: { score: number | null }) {
  const c = useChartColors();
  const tone = scoreTone(score);
  const color = { good: c.good, warning: c.warning, critical: c.critical, neutral: c.neutral }[tone];
  const pct = score ?? 0;
  const r = 42;
  const circ = 2 * Math.PI * r;
  return (
    <div className="relative h-28 w-28 shrink-0">
      <svg viewBox="0 0 100 100" className="h-full w-full -rotate-90">
        <circle cx="50" cy="50" r={r} fill="none" stroke={c.grid} strokeWidth="8" />
        <circle cx="50" cy="50" r={r} fill="none" stroke={color} strokeWidth="8" strokeLinecap="round" strokeDasharray={`${(pct / 100) * circ} ${circ}`} />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-semibold tabular-nums text-ink-900 dark:text-white">{formatScore(score)}</span>
        <span className="text-[10px] font-medium uppercase tracking-wide text-ink-500">Reliability</span>
      </div>
    </div>
  );
}

/** Detail view for original evidence-based (version 1) verifications. */
export function LegacyDetail({ record, setData }: { record: Verification; setData: (r: Verification) => void }) {
  const navigate = useNavigate();
  const [filter, setFilter] = useState<Verdict | 'all'>('all');
  const [focused, setFocused] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  const segments = useMemo(() => (record ? highlightClaims(record.answer, record.claims) : []), [record]);

  const claimsById = Object.fromEntries(record.claims.map((c) => [c.id, c]));
  const visible = record.claims.filter((c) => filter === 'all' || effectiveVerdict(c) === filter);

  async function exportReport(format: 'markdown' | 'json') {
    setActionError(null);
    try {
      await downloadFile(`/api/verifications/${record.id}/report?format=${format}`, `verification-report-${record.id.slice(0, 8)}.${format === 'json' ? 'json' : 'md'}`);
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Export failed.');
    }
  }

  async function remove() {
    if (!window.confirm('Delete this verification permanently? This cannot be undone.')) return;
    setDeleting(true);
    try {
      await api(`/api/verifications/${record.id}`, { method: 'DELETE' });
      navigate('/history');
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Delete failed.');
      setDeleting(false);
    }
  }

  function focusClaim(claimId: string) {
    setFilter('all');
    setFocused(claimId);
    setTimeout(() => document.getElementById(`claim-${claimId}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 50);
  }

  return (
    <>
      <Link to="/history" className="mb-4 inline-flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-900 dark:hover:text-white">
        <ArrowLeft className="h-4 w-4" /> History
      </Link>
      <PageHeader
        title={record.title}
        description={<>Verified {formatDate(record.verified_at ?? record.created_at)} · {(record.duration_ms / 1000).toFixed(1)}s</>}
        actions={
          <>
            <Button variant="secondary" icon={<FileDown className="h-4 w-4" />} onClick={() => exportReport('markdown')}>Report (.md)</Button>
            <Button variant="secondary" icon={<FileJson className="h-4 w-4" />} onClick={() => exportReport('json')}>JSON</Button>
            <Button variant="ghost" icon={<Trash2 className="h-4 w-4" />} loading={deleting} onClick={remove} aria-label="Delete verification" />
          </>
        }
      />

      {actionError && <div className="mb-4"><Alert tone="error">{actionError}</Alert></div>}
      {record.fallback_reason && record.engine_used === 'offline-heuristic' && (
        <div className="mb-4">
          <Alert tone="warning" title="Produced by the offline heuristic, not an AI model">
            {record.engine_requested === 'auto' ? `Live verification was not used: ${record.fallback_reason}` : record.fallback_reason}
          </Alert>
        </div>
      )}

      <Card className="mb-6">
        <CardBody className="flex flex-col gap-6 sm:flex-row sm:items-center">
          <ScoreRing score={record.summary.reliability_score} />
          <div className="flex-1">
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <EngineBadge engine={record.engine_used} isSample={record.is_sample} />
              {record.model && <span className="font-mono text-xs text-ink-500">{record.model}</span>}
            </div>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {VERDICTS.map((v) => {
                const { Icon, label } = VERDICT_META[v];
                const active = filter === v;
                return (
                  <button key={v} onClick={() => setFilter(active ? 'all' : v)} className={`rounded-lg border p-3 text-left transition ${active ? 'border-brand-500 ring-1 ring-brand-500' : 'border-ink-200 hover:border-ink-300 dark:border-ink-700'}`} aria-pressed={active}>
                    <span className="flex items-center gap-1.5 text-xs font-medium text-ink-500"><Icon className="h-3.5 w-3.5" />{label}</span>
                    <span className="mt-1 block text-xl font-semibold tabular-nums text-ink-900 dark:text-white">{record.summary.counts[v]}</span>
                  </button>
                );
              })}
            </div>
            <p className="mt-3 text-xs text-ink-500">
              {record.summary.total_claims} claims · {record.summary.reviewed_claims} human-reviewed · {record.summary.needs_review} awaiting review
            </p>
          </div>
        </CardBody>
      </Card>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-5">
        <div className="space-y-6 xl:col-span-2">
          <Card>
            <CardHeader title="Answer with claim highlights" subtitle="Click a highlight to jump to its claim" />
            <CardBody>
              {record.question && <p className="mb-3 rounded-lg bg-ink-50 p-3 text-sm text-ink-600 dark:bg-ink-800/60 dark:text-ink-300"><strong>Q:</strong> {record.question}</p>}
              <p className="whitespace-pre-wrap text-sm leading-7 text-ink-800 dark:text-ink-200">
                {segments.map((s, i) => {
                  const claim = s.claimId ? claimsById[s.claimId] : null;
                  if (!claim) return <span key={i}>{s.text}</span>;
                  return (
                    <span
                      key={i}
                      role="button"
                      tabIndex={0}
                      onClick={() => focusClaim(claim.id)}
                      onKeyDown={(e) => e.key === 'Enter' && focusClaim(claim.id)}
                      className={`cursor-pointer rounded px-0.5 underline decoration-2 underline-offset-4 [box-decoration-break:clone] ${HIGHLIGHT[effectiveVerdict(claim)]}`}
                      title={`${claim.id}: ${VERDICT_META[effectiveVerdict(claim)].label}`}
                    >
                      {s.text}
                    </span>
                  );
                })}
              </p>
              {record.engine_used === 'live' && <p className="mt-3 text-xs text-ink-500">Live claims are rewritten to be self-contained, so not all of them map to an exact passage.</p>}
            </CardBody>
          </Card>
          <Card>
            <CardHeader title="Evidence sources" />
            <ul className="divide-y divide-ink-100 dark:divide-ink-800">
              {record.evidence.map((e) => (
                <li key={e.id} className="px-5 py-3">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-semibold text-ink-500">{e.id}</span>
                    <span className="text-sm font-medium text-ink-900 dark:text-white">{e.title}</span>
                    {e.source_url && <a href={e.source_url} target="_blank" rel="noreferrer noopener" className="text-ink-400 hover:text-brand-600" aria-label="Open source"><ExternalLink className="h-3.5 w-3.5" /></a>}
                  </div>
                  <p className="mt-1 line-clamp-4 text-xs leading-relaxed text-ink-500 dark:text-ink-400">{e.content}</p>
                </li>
              ))}
            </ul>
          </Card>
        </div>

        <div className="space-y-3 xl:col-span-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-ink-900 dark:text-white">
              Claims {filter !== 'all' && <span className="font-normal text-ink-500">· {VERDICT_META[filter].label}</span>}
            </h2>
            {filter !== 'all' && <button className="text-xs font-medium text-brand-700 hover:underline dark:text-brand-400" onClick={() => setFilter('all')}>Show all</button>}
          </div>
          {visible.length === 0 && <Card><p className="p-6 text-center text-sm text-ink-500">No claims with this verdict.</p></Card>}
          {visible.map((claim) => (
            <ClaimCard key={claim.id} verificationId={record.id} claim={claim} onUpdated={setData} highlighted={focused === claim.id} defaultOpen={focused === claim.id} />
          ))}
        </div>
      </div>
    </>
  );
}
