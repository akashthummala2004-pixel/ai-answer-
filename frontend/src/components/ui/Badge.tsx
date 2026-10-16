import type { ReactNode } from 'react';
import { CheckCircle2, CircleSlash, FlaskConical, HelpCircle, Radio, Shield, ShieldAlert, ShieldCheck, UserSearch, XCircle } from 'lucide-react';
import type { Assessment, ContentType, EngineUsed, RiskLevel, Verdict } from '../../lib/types';

type Tone = 'neutral' | 'brand' | 'good' | 'warning' | 'critical' | 'info';

const TONES: Record<Tone, string> = {
  neutral: 'bg-ink-100 text-ink-700 ring-ink-200 dark:bg-ink-800 dark:text-ink-300 dark:ring-ink-700',
  brand: 'bg-brand-50 text-brand-700 ring-brand-200 dark:bg-brand-500/10 dark:text-brand-300 dark:ring-brand-500/30',
  good: 'bg-green-50 text-green-800 ring-green-200 dark:bg-green-500/10 dark:text-green-300 dark:ring-green-500/30',
  warning: 'bg-amber-50 text-amber-800 ring-amber-200 dark:bg-amber-500/10 dark:text-amber-300 dark:ring-amber-500/30',
  critical: 'bg-red-50 text-red-800 ring-red-200 dark:bg-red-500/10 dark:text-red-300 dark:ring-red-500/30',
  info: 'bg-sky-50 text-sky-800 ring-sky-200 dark:bg-sky-500/10 dark:text-sky-300 dark:ring-sky-500/30',
};

export function Badge({ tone = 'neutral', icon, children, title }: { tone?: Tone; icon?: ReactNode; children: ReactNode; title?: string }) {
  return (
    <span title={title} className={`inline-flex items-center gap-1 whitespace-nowrap rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${TONES[tone]}`}>
      {icon}
      {children}
    </span>
  );
}

export const VERDICT_META: Record<Verdict, { label: string; tone: Tone; Icon: typeof CheckCircle2; color: 'good' | 'critical' | 'warning' | 'neutral' }> = {
  supported: { label: 'Supported', tone: 'good', Icon: CheckCircle2, color: 'good' },
  contradicted: { label: 'Contradicted', tone: 'critical', Icon: XCircle, color: 'critical' },
  uncertain: { label: 'Uncertain', tone: 'warning', Icon: HelpCircle, color: 'warning' },
  unsupported: { label: 'Unsupported', tone: 'neutral', Icon: CircleSlash, color: 'neutral' },
};

export function VerdictBadge({ verdict }: { verdict: Verdict }) {
  const { label, tone, Icon } = VERDICT_META[verdict];
  return (
    <Badge tone={tone} icon={<Icon className="h-3.5 w-3.5" />}>
      {label}
    </Badge>
  );
}

export function EngineBadge({ engine, isSample }: { engine: EngineUsed; isSample?: boolean }) {
  if (isSample) {
    return <Badge tone="warning" icon={<FlaskConical className="h-3.5 w-3.5" />} title="Illustrative sample data">Sample</Badge>;
  }
  return engine === 'live' ? (
    <Badge tone="brand" icon={<Radio className="h-3.5 w-3.5" />} title="Verified by a live AI model via OpenRouter">Live AI</Badge>
  ) : (
    <Badge tone="info" icon={<FlaskConical className="h-3.5 w-3.5" />} title="Deterministic lexical heuristic — not an AI model">Offline heuristic</Badge>
  );
}

// ---- Smart Verification (v2) ------------------------------------------------------------------
export const ASSESSMENT_META: Record<Assessment, { label: string; tone: Tone; Icon: typeof CheckCircle2 }> = {
  supported_by_evidence: { label: 'Supported by Evidence', tone: 'good', Icon: CheckCircle2 },
  contradicted_by_evidence: { label: 'Contradicted by Evidence', tone: 'critical', Icon: XCircle },
  requires_human_review: { label: 'Requires Human Review', tone: 'warning', Icon: UserSearch },
  not_independently_verified: { label: 'Not Independently Verified', tone: 'neutral', Icon: CircleSlash },
};

export function AssessmentBadge({ assessment }: { assessment: Assessment }) {
  const { label, tone, Icon } = ASSESSMENT_META[assessment];
  return <Badge tone={tone} icon={<Icon className="h-3.5 w-3.5" />}>{label}</Badge>;
}

export const RISK_META: Record<RiskLevel, { label: string; tone: Tone; Icon: typeof ShieldCheck }> = {
  low: { label: 'Low', tone: 'good', Icon: ShieldCheck },
  moderate: { label: 'Moderate', tone: 'neutral', Icon: Shield },
  elevated: { label: 'Elevated', tone: 'warning', Icon: ShieldAlert },
  high: { label: 'High', tone: 'critical', Icon: ShieldAlert },
};

export function RiskBadge({ level, prefix = 'Warning signs' }: { level: RiskLevel; prefix?: string }) {
  const { label, tone, Icon } = RISK_META[level];
  return (
    <Badge tone={tone} icon={<Icon className="h-3.5 w-3.5" />} title="How many warning signs the AI review found. Not proof of wrongdoing.">
      {prefix}: {label}
    </Badge>
  );
}

export const CONTENT_TYPE_LABELS: Record<ContentType, string> = {
  ai_answer: 'AI-generated answer',
  email: 'Email',
  business_message: 'Business message',
  document: 'Document',
  screenshot: 'Screenshot',
  web_content: 'Web content',
  other: 'Content',
};
