import { Link } from 'react-router-dom';
import { ArrowRight, PlusCircle, ShieldCheck } from 'lucide-react';
import { VerificationTable } from '../components/VerificationTable';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { Alert, EmptyState, Skeleton } from '../components/ui/Feedback';
import { formatDate } from '../lib/format';
import type { Stats, VerificationListItem } from '../lib/types';
import { useApi } from '../lib/useApi';

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="px-5 py-4">
      <p className="text-xs font-medium text-ink-500 dark:text-ink-400">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums text-ink-900 dark:text-white">{value}</p>
    </div>
  );
}

export default function Dashboard() {
  const stats = useApi<Stats>('/api/stats');
  const list = useApi<VerificationListItem[]>('/api/verifications');
  const s = stats.data;
  const items = list.data ?? [];

  return (
    <div className="mx-auto max-w-5xl">
      <section className="relative overflow-hidden rounded-2xl border border-ink-200 bg-gradient-to-br from-white via-white to-brand-50 px-6 py-12 text-center shadow-card sm:px-12 dark:border-ink-800 dark:from-ink-900 dark:via-ink-900 dark:to-brand-950/40">
        <img src="/mindmasters-mark.png" alt="" className="mx-auto mb-5 h-14 w-14 rounded-2xl bg-white object-contain p-1.5 shadow-sm ring-1 ring-ink-200 dark:ring-ink-700" />
        <h1 className="text-3xl font-semibold tracking-tight text-ink-900 sm:text-4xl dark:text-white">Verify Before You Trust</h1>
        <p className="mx-auto mt-3 max-w-xl text-base text-ink-600 dark:text-ink-300">
          Analyze AI-generated answers, business messages, emails, documents, and online claims in one place.
        </p>
        <Link to="/verify" className="mt-8 inline-block">
          <Button className="h-12 px-7 text-base shadow-md" icon={<PlusCircle className="h-5 w-5" />}>New Verification</Button>
        </Link>
      </section>

      {(stats.error || list.error) && (
        <div className="mt-6">
          <Alert tone="error" title="Could not load your history" action={<Button size="sm" variant="secondary" onClick={() => { void stats.reload(); void list.reload(); }}>Retry</Button>}>
            {stats.error || list.error}
          </Alert>
        </div>
      )}

      <Card className="mt-6">
        {!s ? (
          <div className="p-5"><Skeleton className="h-14" /></div>
        ) : (
          <div className="grid grid-cols-2 divide-ink-100 sm:grid-cols-4 sm:divide-x dark:divide-ink-800">
            <Metric label="Verifications" value={s.total_verifications} />
            <Metric label="Last 7 days" value={s.last_7_days} />
            <Metric label="Awaiting your review" value={s.pending_reviews} />
            <Metric label="Last verification" value={s.last_verification_at ? formatDate(s.last_verification_at).split(',')[0] : '—'} />
          </div>
        )}
      </Card>

      <Card className="mt-6">
        <div className="flex items-center justify-between border-b border-ink-100 px-5 py-4 dark:border-ink-800">
          <h2 className="text-sm font-semibold text-ink-900 dark:text-white">Recent verifications</h2>
          {items.length > 0 && (
            <Link to="/history" className="inline-flex items-center gap-1 text-sm font-medium text-brand-700 hover:underline dark:text-brand-400">
              View history <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          )}
        </div>
        {list.loading && !list.data ? (
          <div className="p-5"><Skeleton className="h-32" /></div>
        ) : items.length === 0 ? (
          <EmptyState icon={<ShieldCheck className="h-8 w-8" />} title="No verifications yet" description="Your verification history will appear here." />
        ) : (
          <VerificationTable items={items.slice(0, 6)} compact />
        )}
      </Card>
    </div>
  );
}
