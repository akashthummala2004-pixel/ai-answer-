import type { ReactNode } from 'react';
import { AlertTriangle, CheckCircle2, Info, Loader2, XCircle } from 'lucide-react';

export function Spinner({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-3 py-16 text-sm text-ink-500 dark:text-ink-400" role="status">
      <Loader2 className="h-5 w-5 animate-spin text-brand-600" />
      {label}
    </div>
  );
}

export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-ink-200/70 dark:bg-ink-800 ${className}`} />;
}

export function EmptyState({ icon, title, description, action }: { icon: ReactNode; title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-14 text-center">
      <div className="mb-4 rounded-2xl bg-ink-100 p-4 text-ink-500 dark:bg-ink-800 dark:text-ink-400">{icon}</div>
      <h3 className="text-base font-semibold text-ink-900 dark:text-white">{title}</h3>
      {description && <p className="mt-1 max-w-md text-sm text-ink-500 dark:text-ink-400">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

type Tone = 'info' | 'success' | 'warning' | 'error';
const ALERT: Record<Tone, { cls: string; Icon: typeof Info }> = {
  info: { cls: 'border-sky-200 bg-sky-50 text-sky-900 dark:border-sky-500/30 dark:bg-sky-500/10 dark:text-sky-200', Icon: Info },
  success: { cls: 'border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-200', Icon: CheckCircle2 },
  warning: { cls: 'border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200', Icon: AlertTriangle },
  error: { cls: 'border-red-200 bg-red-50 text-red-900 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-200', Icon: XCircle },
};

export function Alert({ tone = 'info', title, children, action }: { tone?: Tone; title?: string; children?: ReactNode; action?: ReactNode }) {
  const { cls, Icon } = ALERT[tone];
  return (
    <div className={`flex gap-3 rounded-xl border px-4 py-3 text-sm ${cls}`} role={tone === 'error' ? 'alert' : 'status'}>
      <Icon className="mt-0.5 h-4 w-4 shrink-0" />
      <div className="min-w-0 flex-1">
        {title && <p className="font-semibold">{title}</p>}
        {children && <div className={title ? 'mt-0.5 opacity-90' : ''}>{children}</div>}
      </div>
      {action}
    </div>
  );
}
