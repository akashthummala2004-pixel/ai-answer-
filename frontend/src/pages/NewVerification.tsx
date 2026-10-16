import { useEffect, useRef, useState, type DragEvent, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { FileText, ImageIcon, Loader2, ShieldCheck, Sparkles, UploadCloud, X } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { Card, CardBody } from '../components/ui/Card';
import { Alert } from '../components/ui/Feedback';
import { useApp } from '../context/AppContext';
import { api, ApiError } from '../lib/api';
import { formatBytes, validateFile, MAX_FILES, MAX_TEXT_CHARS } from '../lib/upload';
import type { SmartVerification } from '../lib/types';

const SAMPLE = `Subject: Urgent: your parcel is on hold

Dear Customer,
We attempted to deliver your parcel (ref. AC-20931) but customs duties of $4.99 are unpaid.
Pay within 24 hours at http://acme-parcel-release.xyz/pay or the parcel will be returned.
Our refund policy guarantees all payments are refunded within 30 days.

Acme Logistics Support Team
support@acme-logistics-help.com`;

const STAGES = ['Reading your content…', 'Identifying claims and key details…', 'Analysing with AI…', 'Preparing your results…'];

interface Picked {
  file: File;
  preview: string | null;
}

export default function NewVerification() {
  const { health } = useApp();
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const [text, setText] = useState('');
  const [files, setFiles] = useState<Picked[]>([]);
  const [fileErrors, setFileErrors] = useState<string[]>([]);
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [stage, setStage] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const aiReady = health?.ai_mode === 'live';
  const hasImages = files.some((f) => f.file.type.startsWith('image/'));
  const visionBlocked = hasImages && health?.vision_supported === false;
  const textTooLong = text.length > MAX_TEXT_CHARS;
  const canSubmit = aiReady && !busy && !visionBlocked && !textTooLong && (text.trim().length > 0 || files.length > 0);

  useEffect(() => () => files.forEach((f) => f.preview && URL.revokeObjectURL(f.preview)), []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!busy) return;
    setStage(0);
    const t = setInterval(() => setStage((s) => Math.min(s + 1, STAGES.length - 1)), 6000);
    return () => clearInterval(t);
  }, [busy]);

  function addFiles(list: FileList | File[]) {
    const errors: string[] = [];
    const next = [...files];
    for (const file of Array.from(list)) {
      const problem = validateFile(file, next.map((p) => p.file));
      if (problem) {
        errors.push(problem);
        continue;
      }
      next.push({ file, preview: file.type.startsWith('image/') ? URL.createObjectURL(file) : null });
    }
    setFiles(next);
    setFileErrors(errors);
    setError(null);
  }

  function removeFile(index: number) {
    const target = files[index];
    if (target.preview) URL.revokeObjectURL(target.preview);
    setFiles(files.filter((_, i) => i !== index));
    setFileErrors([]);
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDragging(false);
    if (!busy) addFiles(e.dataTransfer.files);
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setBusy(true);
    setError(null);
    const form = new FormData();
    if (text.trim()) form.append('text', text.trim());
    files.forEach((f) => form.append('files', f.file, f.file.name));
    try {
      const record = await api<SmartVerification>('/api/smart-verifications', { method: 'POST', form, timeoutMs: 180_000 });
      navigate(`/verifications/${record.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'The verification could not be completed. Please try again.');
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="mx-auto max-w-3xl">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-ink-900 dark:text-white">New verification</h1>
        <p className="mt-1 text-sm text-ink-500 dark:text-ink-400">Paste text, upload a document or screenshot — or both. We'll analyse it and flag what needs checking.</p>
      </div>

      {!aiReady && (
        <div className="mb-4">
          <Alert tone="warning" title="AI analysis is unavailable">The verification service is not connected to its AI provider. Please contact your administrator.</Alert>
        </div>
      )}

      <Card>
        <CardBody className="space-y-6">
          <div>
            <div className="mb-1.5 flex items-baseline justify-between">
              <label htmlFor="content" className="text-sm font-medium text-ink-800 dark:text-ink-200">Text or information</label>
              <button type="button" className="text-xs font-medium text-brand-700 hover:underline disabled:opacity-50 dark:text-brand-400" disabled={busy} onClick={() => setText(SAMPLE)}>
                Use a sample email
              </button>
            </div>
            <textarea
              id="content"
              className="field min-h-[220px] resize-y text-[15px] leading-relaxed"
              placeholder="Paste an AI-generated answer, email, business message, or information you want to verify..."
              value={text}
              disabled={busy}
              onChange={(e) => setText(e.target.value)}
            />
            <p className={`mt-1 text-right text-xs tabular-nums ${textTooLong ? 'text-red-600' : 'text-ink-400'}`}>
              {text.length.toLocaleString()} / {MAX_TEXT_CHARS.toLocaleString()} characters
            </p>
          </div>

          <div>
            <p className="mb-1.5 text-sm font-medium text-ink-800 dark:text-ink-200">Upload document or screenshot <span className="font-normal text-ink-400">(optional)</span></p>
            <div
              role="button"
              tabIndex={0}
              aria-label="Upload files"
              onClick={() => !busy && inputRef.current?.click()}
              onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && !busy && inputRef.current?.click()}
              onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={onDrop}
              className={`flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-8 text-center transition ${
                dragging ? 'border-brand-500 bg-brand-50/60 dark:bg-brand-500/10' : 'border-ink-200 hover:border-brand-400 hover:bg-ink-50 dark:border-ink-700 dark:hover:bg-ink-800/40'
              } ${busy ? 'pointer-events-none opacity-60' : ''}`}
            >
              <UploadCloud className="h-8 w-8 text-brand-600" />
              <p className="mt-2 text-sm font-medium text-ink-800 dark:text-ink-200">Drop files here or <span className="text-brand-700 dark:text-brand-400">browse</span></p>
              <p className="mt-1 text-xs text-ink-500">PDF up to 10 MB · PNG, JPG or WebP up to 5 MB · up to {MAX_FILES} files</p>
              <input
                ref={inputRef}
                type="file"
                multiple
                hidden
                accept=".pdf,.png,.jpg,.jpeg,.webp,application/pdf,image/png,image/jpeg,image/webp"
                onChange={(e) => { if (e.target.files) addFiles(e.target.files); e.target.value = ''; }}
              />
            </div>

            {fileErrors.length > 0 && (
              <div className="mt-3"><Alert tone="error">{fileErrors.map((m, i) => <p key={i}>{m}</p>)}</Alert></div>
            )}

            {files.length > 0 && (
              <ul className="mt-3 grid gap-2 sm:grid-cols-2">
                {files.map((f, i) => (
                  <li key={`${f.file.name}-${i}`} className="flex items-center gap-3 rounded-lg border border-ink-200 bg-white p-2 dark:border-ink-700 dark:bg-ink-900">
                    {f.preview ? (
                      <img src={f.preview} alt="" className="h-12 w-12 shrink-0 rounded-md border border-ink-200 object-cover dark:border-ink-700" />
                    ) : (
                      <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-md bg-red-50 text-red-600 dark:bg-red-500/10"><FileText className="h-6 w-6" /></div>
                    )}
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-ink-900 dark:text-white" title={f.file.name}>{f.file.name}</p>
                      <p className="flex items-center gap-1 text-xs text-ink-500">
                        {f.preview ? <ImageIcon className="h-3 w-3" /> : <FileText className="h-3 w-3" />}
                        {f.preview ? 'Image' : 'PDF'} · {formatBytes(f.file.size)}
                      </p>
                    </div>
                    <button type="button" disabled={busy} onClick={() => removeFile(i)} className="rounded-md p-1.5 text-ink-400 hover:bg-ink-100 hover:text-ink-700 disabled:opacity-50 dark:hover:bg-ink-800" aria-label={`Remove ${f.file.name}`}>
                      <X className="h-4 w-4" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {visionBlocked && (
              <div className="mt-3"><Alert tone="warning">The configured AI model cannot read images, so screenshots can't be analysed. Remove the image or ask your administrator to enable an image-capable model.</Alert></div>
            )}
          </div>

          {error && <Alert tone="error" title="Verification failed">{error}</Alert>}

          <div className="flex flex-col items-stretch gap-3 border-t border-ink-100 pt-5 sm:flex-row sm:items-center sm:justify-between dark:border-ink-800">
            <p className="flex items-start gap-2 text-xs text-ink-500">
              <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-brand-600" />
              Files are processed for this verification only and are not stored. Results are saved to your private history.
            </p>
            <Button type="submit" disabled={!canSubmit} className="h-11 px-6 text-[15px]" icon={busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}>
              {busy ? 'Verifying…' : 'Generate Verification'}
            </Button>
          </div>
          {busy && (
            <div className="rounded-lg bg-brand-50/70 px-4 py-3 text-sm text-brand-800 dark:bg-brand-500/10 dark:text-brand-200" role="status">
              <p className="font-medium">{STAGES[stage]}</p>
              <p className="mt-0.5 text-xs opacity-80">This usually takes 10–40 seconds. Please keep this page open.</p>
            </div>
          )}
        </CardBody>
      </Card>
    </form>
  );
}
