import { Link } from 'react-router-dom';
import { ArrowUpRight, ClipboardCheck } from 'lucide-react';
import { ClaimCard } from '../components/ClaimCard';
import { SmartClaimCard } from '../components/smart/SmartClaimCard';
import { Button } from '../components/ui/Button';
import { Card, PageHeader } from '../components/ui/Card';
import { Alert, EmptyState, Skeleton } from '../components/ui/Feedback';
import type { Claim, QueueItem, SmartClaim } from '../lib/types';
import { useApi } from '../lib/useApi';

export default function ReviewQueue() {
  const { data, error, loading, reload } = useApi<QueueItem[]>('/api/review-queue');

  return (
    <>
      <PageHeader
        title="Review queue"
        description="Claims flagged for a person to check before anyone relies on them."
      />
      {error && <Alert tone="error" title="Could not load the queue" action={<Button size="sm" variant="secondary" onClick={reload}>Retry</Button>}>{error}</Alert>}
      {loading && !data && <Skeleton className="h-64" />}
      {data && data.length === 0 && (
        <Card><EmptyState icon={<ClipboardCheck className="h-8 w-8" />} title="All caught up" description="No claims currently need human review." /></Card>
      )}
      <div className="space-y-6">
        {Object.entries(
          (data ?? []).reduce<Record<string, QueueItem[]>>((acc, item) => {
            (acc[item.verification_id] ||= []).push(item);
            return acc;
          }, {}),
        ).map(([vid, items]) => (
          <section key={vid}>
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <Link to={`/verifications/${vid}`} className="inline-flex items-center gap-1 text-sm font-semibold text-ink-900 hover:text-brand-700 dark:text-white dark:hover:text-brand-400">
                {items[0].verification_title}
                <ArrowUpRight className="h-3.5 w-3.5" />
              </Link>
              <span className="text-xs text-ink-500">{items.length} pending</span>
            </div>
            <div className="space-y-3">
              {/* A saved review removes the claim from the queue, so refresh after each one. */}
              {items.map((item) =>
                item.version === 2 ? (
                  <SmartClaimCard key={item.claim.id} verificationId={vid} claim={item.claim as SmartClaim} sourceLabels={{}} onUpdated={() => void reload()} />
                ) : (
                  <ClaimCard key={item.claim.id} verificationId={vid} claim={item.claim as Claim} onUpdated={() => void reload()} />
                ),
              )}
            </div>
          </section>
        ))}
      </div>
    </>
  );
}
