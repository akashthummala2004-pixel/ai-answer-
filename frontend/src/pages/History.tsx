import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { History as HistoryIcon, PlusCircle, Search } from 'lucide-react';
import { VerificationTable } from '../components/VerificationTable';
import { Button } from '../components/ui/Button';
import { Card, PageHeader } from '../components/ui/Card';
import { Alert, EmptyState, Skeleton } from '../components/ui/Feedback';
import type { VerificationListItem } from '../lib/types';
import { useApi } from '../lib/useApi';

export default function History() {
  const { data, error, loading, reload } = useApi<VerificationListItem[]>('/api/verifications');
  const [query, setQuery] = useState('');
  const [engine, setEngine] = useState('all');
  const [status, setStatus] = useState('all');

  const filtered = useMemo(
    () =>
      (data ?? []).filter(
        (v) =>
          v.title.toLowerCase().includes(query.trim().toLowerCase()) &&
          (engine === 'all' || (engine === 'smart' ? v.version === 2 : v.version !== 2)) &&
          (status === 'all' || v.status === status),
      ),
    [data, query, engine, status],
  );

  return (
    <>
      <PageHeader title="Verification history" description="Reopen any previous verification, review its claims, or download its report." />
      {error && <Alert tone="error" title="Could not load history" action={<Button size="sm" variant="secondary" onClick={reload}>Retry</Button>}>{error}</Alert>}
      {!error && (
        <Card>
          <div className="flex flex-wrap items-center gap-3 border-b border-ink-100 p-4 dark:border-ink-800">
            <div className="relative min-w-[200px] flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400" />
              <input className="field pl-9" placeholder="Search by title…" value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Search" />
            </div>
            <select className="field w-auto" value={engine} onChange={(e) => setEngine(e.target.value)} aria-label="Type filter">
              <option value="all">All types</option>
              <option value="smart">Smart verifications</option>
              <option value="legacy">Earlier evidence checks</option>
            </select>
            <select className="field w-auto" value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Status filter">
              <option value="all">All statuses</option>
              <option value="needs_review">Needs review</option>
              <option value="reviewed">Reviewed</option>
              <option value="complete">Complete</option>
            </select>
          </div>
          {loading && !data ? (
            <div className="p-5"><Skeleton className="h-48" /></div>
          ) : data && data.length === 0 ? (
            <EmptyState icon={<HistoryIcon className="h-8 w-8" />} title="History is empty" description="Run your first verification to see it here." action={<Link to="/verify"><Button icon={<PlusCircle className="h-4 w-4" />}>New verification</Button></Link>} />
          ) : (
            <VerificationTable items={filtered} />
          )}
        </Card>
      )}
    </>
  );
}
