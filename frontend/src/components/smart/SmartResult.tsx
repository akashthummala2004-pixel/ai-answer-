import { useState, type ReactNode } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AlertTriangle, ArrowLeft, ChevronDown, ClipboardList, Download, FileJson, FileText, Info, ListChecks, Loader2, Search, ShieldAlert, Trash2 } from 'lucide-react';
import { SmartClaimCard, effectiveAssessment } from './SmartClaimCard';
import { ASSESSMENT_META, Badge, CONTENT_TYPE_LABELS, RiskBadge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { Card, CardBody } from '../ui/Card';
import { Alert } from '../ui/Feedback';
import { api, ApiError, downloadFile } from '../../lib/api';
import { formatDate } from '../../lib/format';
import { ASSESSMENTS, type Assessment, type SmartInput, type SmartVerification } from '../../lib/types';

const SEVERITY_TONE = { high: 'critical', medium: 'warning', low: 'neutral' } as const;

function inputLabel(i: SmartInput): string {
  if (i.kind === 'text') return 'your text';
  return i.kind === 'image' ? `image “${i.name}”` : `“${i.name}”`;
}

function Section({ letter, title, icon, children, aside }: { letter: string; title: string; icon: ReactNode; children: ReactNode; aside?: ReactNode }) {
  return (
    <section className="scroll-mt-24" id={`section-${letter}`}>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-base font-semibold text-ink-900 dark:text-white">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-50 text-brand-700 dark:bg-brand-500/10 dark:text-brand-300">{icon}</span>
          {title}
        </h2>
        {aside}
      </div>
      {children}
    </section>
  );
}

export function SmartResult({ record, setData }: { record: SmartVerification; setData: (r: SmartVerification) => void }) {
  const navigate = useNavigate();
  const [downloading, setDownloading] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Assessment | 'all'>('all');
  const [showText, setShowText] = useState(false);
  const a = record.analysis;
  const labels = Object.fromEntries(record.inputs.map((i) => [i.id, inputLabel(i)]));
  const claims = record.claims.filter((c) => filter === 'all' || effectiveAssessment(c) === filter);
  const counts = record.summary.counts;

  async function download(format: 'pdf' | 'markdown' | 'json') {
    setDownloading(format);
    setActionError(null);
    const ext = { pdf: 'pdf', markdown: 'md', json: 'json' }[format];
    try {
      await downloadFile(`/api/verifications/${record.id}/report?format=${format}`, `verification-report-${record.id.slice(0, 8)}.${ext}`);
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Download failed.');
    } finally {
      setDownloading(null);
    }
  }

  async function remove() {
    if (!window.confirm('Delete this verification permanently? This cannot be undone.')) return;
    try {
      await api(`/api/verifications/${record.id}`, { method: 'DELETE' });
      navigate('/history');
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Delete failed.');
    }
  }

  return (
    <div className="mx-auto max-w-5xl">
      <Link to="/history" className="mb-4 inline-flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-900 dark:hover:text-white"><ArrowLeft className="h-4 w-4" /> History</Link>

      <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wider text-brand-700 dark:text-brand-400">{CONTENT_TYPE_LABELS[a.content_type]} · Verification report</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-ink-900 dark:text-white">{record.title}</h1>
          <p className="mt-1 text-sm text-ink-500">{formatDate(record.verified_at)} · ID {record.id.slice(0, 8)} · {record.inputs.map((i) => (i.kind === 'text' ? 'Text' : i.name)).join(', ')}</p>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          <Button onClick={() => download('pdf')} loading={downloading === 'pdf'} icon={<Download className="h-4 w-4" />} className="h-11 px-5">Download PDF Report</Button>
          <Button variant="secondary" size="sm" onClick={() => download('markdown')} loading={downloading === 'markdown'} icon={<FileText className="h-3.5 w-3.5" />}>Markdown</Button>
          <Button variant="secondary" size="sm" onClick={() => download('json')} loading={downloading === 'json'} icon={<FileJson className="h-3.5 w-3.5" />}>JSON</Button>
          <Button variant="ghost" size="sm" onClick={remove} icon={<Trash2 className="h-4 w-4" />} aria-label="Delete verification" />
        </div>
      </div>

      {actionError && <div className="mb-4"><Alert tone="error">{actionError}</Alert></div>}
      {downloading && <p className="mb-4 flex items-center gap-2 text-xs text-ink-500"><Loader2 className="h-3.5 w-3.5 animate-spin" />Preparing your download…</p>}

      <div className="space-y-8">
        <Section letter="A" title="Overall Assessment" icon={<Info className="h-4 w-4" />} aside={<RiskBadge level={a.risk_level} />}>
          <Card>
            <CardBody className="space-y-4">
              <p className="text-[15px] leading-relaxed text-ink-800 dark:text-ink-200">{a.overall_assessment}</p>
              <div className="rounded-lg bg-ink-50 p-3 text-sm text-ink-600 dark:bg-ink-800/50 dark:text-ink-300">
                <span className="font-medium text-ink-800 dark:text-ink-200">What was submitted: </span>{a.summary}
              </div>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                {ASSESSMENTS.map((key) => {
                  const { label, Icon } = ASSESSMENT_META[key];
                  const active = filter === key;
                  return (
                    <button key={key} onClick={() => { setFilter(active ? 'all' : key); document.getElementById('section-D')?.scrollIntoView({ behavior: 'smooth' }); }}
                      className={`rounded-lg border p-3 text-left transition ${active ? 'border-brand-500 ring-1 ring-brand-500' : 'border-ink-200 hover:border-ink-300 dark:border-ink-700'}`} aria-pressed={active}>
                      <span className="flex items-center gap-1.5 text-xs font-medium text-ink-500"><Icon className="h-3.5 w-3.5" />{label}</span>
                      <span className="mt-1 block text-xl font-semibold tabular-nums text-ink-900 dark:text-white">{counts[key]}</span>
                    </button>
                  );
                })}
              </div>
              <p className="flex items-start gap-2 text-xs text-ink-500">
                <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                AI-assisted assessment by {record.model}. The warning-sign level reflects what the review noticed — it is not proof of wrongdoing.
              </p>
            </CardBody>
          </Card>
        </Section>

        <Section letter="B" title="Key Findings" icon={<ListChecks className="h-4 w-4" />}>
          <Card>
            {a.key_findings.length === 0 && a.detected_details.length === 0 ? (
              <p className="p-5 text-sm text-ink-500">No key details were identified.</p>
            ) : (
              <>
                {a.key_findings.length > 0 && (
                  <dl className="divide-y divide-ink-100 dark:divide-ink-800">
                    {a.key_findings.map((f, i) => (
                      <div key={i} className="grid gap-1 px-5 py-3 sm:grid-cols-[180px_1fr] sm:gap-4">
                        <dt className="text-sm font-medium text-ink-900 dark:text-white">{f.label}</dt>
                        <dd className="text-sm text-ink-700 dark:text-ink-300">{f.detail}{f.source && labels[f.source] && <span className="ml-2 text-xs text-ink-400">— {labels[f.source]}</span>}</dd>
                      </div>
                    ))}
                  </dl>
                )}
                {a.detected_details.length > 0 && (
                  <div className="border-t border-ink-100 px-5 py-4 dark:border-ink-800">
                    <p className="mb-2 text-xs font-medium text-ink-500">Detected automatically in the content</p>
                    <div className="flex flex-wrap gap-2">
                      {a.detected_details.map((d, i) => (
                        <span key={i} className="inline-flex max-w-full items-center gap-1.5 rounded-md bg-ink-100 px-2 py-1 text-xs dark:bg-ink-800">
                          <span className="text-ink-500">{d.type}</span>
                          <span className="truncate font-mono text-ink-800 dark:text-ink-200">{d.value}</span>
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </Card>
        </Section>

        <Section letter="C" title="Potential Risks" icon={<ShieldAlert className="h-4 w-4" />}>
          <Card>
            {a.risks.length === 0 ? (
              <p className="p-5 text-sm text-ink-500">No specific warning signs were identified in the submitted content.</p>
            ) : (
              <ul className="divide-y divide-ink-100 dark:divide-ink-800">
                {a.risks.map((r, i) => (
                  <li key={i} className="flex gap-3 px-5 py-4">
                    <AlertTriangle className={`mt-0.5 h-4 w-4 shrink-0 ${r.severity === 'high' ? 'text-red-600' : r.severity === 'medium' ? 'text-amber-500' : 'text-ink-400'}`} />
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-sm font-semibold text-ink-900 dark:text-white">{r.title}</p>
                        <Badge tone={SEVERITY_TONE[r.severity]}>{r.severity} severity</Badge>
                      </div>
                      <p className="mt-1 text-sm text-ink-600 dark:text-ink-300">{r.detail}</p>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </Section>

        <Section letter="D" title="Claim-by-Claim Analysis" icon={<Search className="h-4 w-4" />}
          aside={filter !== 'all' && <button className="text-xs font-medium text-brand-700 hover:underline dark:text-brand-400" onClick={() => setFilter('all')}>Show all {record.claims.length} claims</button>}>
          <div className="space-y-3">
            {record.claims.length === 0 && <Card><p className="p-5 text-sm text-ink-500">No discrete factual claims were identified.</p></Card>}
            {record.claims.length > 0 && claims.length === 0 && <Card><p className="p-5 text-sm text-ink-500">No claims with this assessment.</p></Card>}
            {claims.map((c) => <SmartClaimCard key={c.id} verificationId={record.id} claim={c} sourceLabels={labels} onUpdated={setData} />)}
          </div>
        </Section>

        <Section letter="E" title="Recommended Next Steps" icon={<ClipboardList className="h-4 w-4" />}>
          <Card>
            <ol className="divide-y divide-ink-100 dark:divide-ink-800">
              {a.next_steps.map((s, i) => (
                <li key={i} className="flex gap-3 px-5 py-3 text-sm text-ink-700 dark:text-ink-300">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-600 text-xs font-semibold text-white">{i + 1}</span>
                  <span className="pt-0.5">{s}</span>
                </li>
              ))}
            </ol>
          </Card>
        </Section>

        <div className="rounded-xl border border-ink-200 bg-ink-50 p-5 dark:border-ink-800 dark:bg-ink-900/60">
          <p className="flex items-center gap-2 text-sm font-semibold text-ink-900 dark:text-white"><Info className="h-4 w-4 text-ink-500" />Verification limitations</p>
          <ul className="mt-2 list-disc space-y-1 pl-6 text-sm text-ink-600 dark:text-ink-400">
            {record.limitations.map((l, i) => <li key={i}>{l}</li>)}
          </ul>
        </div>

        {record.submitted_text && (
          <div>
            <button className="inline-flex items-center gap-1.5 text-sm font-medium text-ink-600 hover:text-ink-900 dark:text-ink-400 dark:hover:text-white" onClick={() => setShowText(!showText)} aria-expanded={showText}>
              <ChevronDown className={`h-4 w-4 transition ${showText ? 'rotate-180' : ''}`} />{showText ? 'Hide' : 'Show'} submitted text
            </button>
            {showText && <pre className="mt-2 max-h-96 overflow-auto whitespace-pre-wrap rounded-xl border border-ink-200 bg-white p-4 font-sans text-sm text-ink-700 dark:border-ink-800 dark:bg-ink-900 dark:text-ink-300">{record.submitted_text}</pre>}
          </div>
        )}
      </div>
    </div>
  );
}
