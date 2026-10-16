import type { ReactNode } from 'react';

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-xl border border-ink-200 bg-white shadow-card dark:border-ink-800 dark:bg-ink-900 ${className}`}>
      {children}
    </div>
  );
}

export function CardHeader({ title, subtitle, action }: { title: ReactNode; subtitle?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3 border-b border-ink-100 px-5 py-4 dark:border-ink-800">
      <div className="min-w-0">
        <h3 className="text-sm font-semibold text-ink-900 dark:text-white">{title}</h3>
        {subtitle && <p className="mt-0.5 text-xs text-ink-500 dark:text-ink-400">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

export function CardBody({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`p-5 ${className}`}>{children}</div>;
}

export function PageHeader({ title, description, actions }: { title: string; description?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-tight text-ink-900 dark:text-white">{title}</h1>
        {description && <p className="mt-1 max-w-3xl text-sm text-ink-500 dark:text-ink-400">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function StatCard({ label, value, hint, icon }: { label: string; value: ReactNode; hint?: ReactNode; icon?: ReactNode }) {
  return (
    <Card className="p-5">
      <div className="flex items-start justify-between">
        <p className="text-sm font-medium text-ink-500 dark:text-ink-400">{label}</p>
        {icon && <div className="rounded-lg bg-brand-50 p-2 text-brand-600 dark:bg-brand-500/10 dark:text-brand-400">{icon}</div>}
      </div>
      <p className="mt-2 text-3xl font-semibold tabular-nums tracking-tight text-ink-900 dark:text-white">{value}</p>
      {hint && <p className="mt-1 text-xs text-ink-500 dark:text-ink-400">{hint}</p>}
    </Card>
  );
}
