import type { ReactNode } from 'react';
import { CheckCircle2, CircleDashed, Moon, Sun } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { Card, CardBody, CardHeader, PageHeader } from '../components/ui/Card';
import { useApp } from '../context/AppContext';
import { useTheme } from '../lib/theme';

function Row({ label, ok, value, help }: { label: string; ok: boolean; value: ReactNode; help: string }) {
  return (
    <div className="flex items-start gap-3 py-3">
      {ok ? <CheckCircle2 className="mt-0.5 h-5 w-5 text-green-600" /> : <CircleDashed className="mt-0.5 h-5 w-5 text-amber-500" />}
      <div className="flex-1">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm font-medium text-ink-900 dark:text-white">{label}</p>
          <p className="text-sm text-ink-600 dark:text-ink-300">{value}</p>
        </div>
        <p className="mt-0.5 text-xs text-ink-500 dark:text-ink-400">{help}</p>
      </div>
    </div>
  );
}

export default function SettingsPage() {
  const { health, retryHealth } = useApp();
  const { theme, toggle } = useTheme();
  if (!health) return null;

  return (
    <>
      <PageHeader title="System & settings" description="Service status. Secrets are configured on the server and never reach the browser." />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title="Integrations" action={<Button size="sm" variant="secondary" onClick={retryHealth}>Refresh</Button>} />
          <CardBody className="divide-y divide-ink-100 py-1 dark:divide-ink-800">
            <Row label="AI analysis (OpenRouter)" ok={health.ai_mode === 'live'} value={health.ai_mode === 'live' ? 'Connected' : 'Not configured'}
              help={health.ai_mode === 'live' ? 'Verifications are analysed by a live AI model. If the AI service fails you see an error — results are never simulated.' : 'Set OPENROUTER_API_KEY in backend/.env to enable verification.'} />
            <Row label="AI model" ok={health.ai_mode === 'live'} value={<code className="font-mono text-xs">{health.default_model}</code>} help="Configured on the server (OPENROUTER_DEFAULT_MODEL)." />
            <Row label="Screenshots and scanned PDFs" ok={health.vision_supported === true}
              value={health.vision_supported === true ? 'Supported' : health.vision_supported === false ? 'Not supported' : 'Unknown'}
              help={health.vision_supported === false ? 'The configured model cannot read images. Use an image-capable model such as openai/gpt-4o-mini.' : 'The configured model accepts image input.'} />
            <Row label="External evidence search" ok={health.web_search} value={health.web_search ? 'Connected' : 'Not connected'}
              help="Without a search service, claims are compared only with the material you submit; others are marked Not Independently Verified." />
            <Row label="Database" ok={health.storage === 'supabase'} value={health.storage === 'supabase' ? 'Supabase PostgreSQL' : 'Local JSON file'}
              help={health.storage === 'supabase' ? 'Results are stored with row-level security: each user sees only their own.' : 'Set SUPABASE_URL and SUPABASE_ANON_KEY to persist history in Supabase.'} />
            <Row label="Authentication" ok={health.auth_required} value={health.auth_required ? 'Supabase Auth' : 'Disabled'} help="Email and password sign-in." />
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Appearance & method" />
          <CardBody className="space-y-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-ink-900 dark:text-white">Theme</p>
                <p className="text-xs text-ink-500">Currently {theme} mode</p>
              </div>
              <Button variant="secondary" size="sm" onClick={toggle} icon={theme === 'dark' ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}>
                Switch to {theme === 'dark' ? 'light' : 'dark'}
              </Button>
            </div>
            <div className="space-y-2 text-sm text-ink-600 dark:text-ink-300">
              <p className="font-medium text-ink-900 dark:text-white">How Smart Verification works</p>
              <p>Text is read directly, text-based PDFs are extracted on the server, and screenshots or scanned pages are read by the AI model. Uploaded files are not stored.</p>
              <p>The AI identifies claims, key details and warning signs. A claim is only marked <strong>Supported</strong> or <strong>Contradicted by Evidence</strong> when the quoted evidence is found in a different input you supplied; otherwise it is <strong>Not Independently Verified</strong> or <strong>Requires Human Review</strong>.</p>
              <p>No accuracy percentage is shown: the system has not been measured against a benchmark, and AI assessments can be wrong.</p>
            </div>
          </CardBody>
        </Card>
      </div>
    </>
  );
}
