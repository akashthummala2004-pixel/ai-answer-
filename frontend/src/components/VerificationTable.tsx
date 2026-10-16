import { useNavigate } from 'react-router-dom';
import { FileText, ImageIcon, Type } from 'lucide-react';
import { Badge, CONTENT_TYPE_LABELS, RiskBadge } from './ui/Badge';
import { formatDate, formatScore } from '../lib/format';
import type { InputKind, SmartSummary, Status, Summary, VerificationListItem } from '../lib/types';

const STATUS: Record<Status, { label: string; tone: 'warning' | 'good' | 'neutral' }> = {
  needs_review: { label: 'Needs review', tone: 'warning' },
  reviewed: { label: 'Reviewed', tone: 'good' },
  complete: { label: 'Complete', tone: 'neutral' },
};

const INPUT_ICON: Record<InputKind, typeof FileText> = { text: Type, pdf: FileText, scanned_pdf: FileText, image: ImageIcon };

function InputIcons({ kinds }: { kinds: InputKind[] }) {
  return (
    <span className="inline-flex gap-1 text-ink-400" aria-label={kinds.join(', ')}>
      {kinds.map((k, i) => {
        const Icon = INPUT_ICON[k];
        return <Icon key={i} className="h-3.5 w-3.5" />;
      })}
    </span>
  );
}

export function VerificationTable({ items, compact = false }: { items: VerificationListItem[]; compact?: boolean }) {
  const navigate = useNavigate();
  if (!items.length) return <p className="px-5 py-8 text-center text-sm text-ink-500">No matching verifications.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px]">
        <thead className="border-b border-ink-100 bg-ink-50/60 dark:border-ink-800 dark:bg-ink-800/40">
          <tr>
            <th className="table-head">Verification</th>
            <th className="table-head">Result</th>
            {!compact && <th className="table-head text-right">Claims</th>}
            <th className="table-head">Status</th>
            <th className="table-head">Date</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-ink-100 dark:divide-ink-800">
          {items.map((v) => {
            const smart = v.version === 2;
            return (
              <tr
                key={v.id}
                onClick={() => navigate(`/verifications/${v.id}`)}
                onKeyDown={(e) => e.key === 'Enter' && navigate(`/verifications/${v.id}`)}
                tabIndex={0}
                className="cursor-pointer transition hover:bg-ink-50 focus:bg-ink-50 focus:outline-none dark:hover:bg-ink-800/50 dark:focus:bg-ink-800/50"
              >
                <td className="table-cell max-w-sm">
                  <p className="truncate font-medium text-ink-900 dark:text-white">{v.title}</p>
                  <p className="mt-0.5 flex items-center gap-2 text-xs text-ink-500">
                    {smart ? CONTENT_TYPE_LABELS[v.content_type ?? 'other'] : 'Evidence check (earlier version)'}
                    {smart && v.input_kinds && <InputIcons kinds={v.input_kinds} />}
                  </p>
                </td>
                <td className="table-cell">
                  {smart ? (
                    <RiskBadge level={(v.summary as SmartSummary).risk_level} />
                  ) : (
                    <span className="text-xs text-ink-500">Reliability {formatScore((v.summary as Summary).reliability_score)}</span>
                  )}
                </td>
                {!compact && <td className="table-cell text-right tabular-nums">{v.summary.total_claims}</td>}
                <td className="table-cell"><Badge tone={STATUS[v.status].tone}>{STATUS[v.status].label}</Badge></td>
                <td className="table-cell whitespace-nowrap text-ink-500">{formatDate(v.created_at)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
