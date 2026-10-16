import { useState, type FormEvent } from 'react';
import { Button } from '../components/ui/Button';
import { Alert } from '../components/ui/Feedback';
import { useApp } from '../context/AppContext';
import { ApiError } from '../lib/api';

export default function Login() {
  const { signIn } = useApp();
  const [mode, setMode] = useState<'login' | 'signup'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setInfo(null);
    if (password.length < 8) return setError('Password must be at least 8 characters.');
    setBusy(true);
    try {
      const message = await signIn(email.trim(), password, mode);
      if (message) setInfo(message);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Sign-in failed.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-brand-50 via-white to-ink-100 px-4 dark:from-ink-950 dark:via-ink-950 dark:to-brand-950/40">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex justify-center">
          <img src="/mindmasters-logo-sm.png" alt="Mind Masters AI Solutions" className="h-28 w-auto rounded-xl bg-white p-2 shadow-sm ring-1 ring-ink-200 dark:ring-ink-700" />
        </div>
        <div className="rounded-2xl border border-ink-200 bg-white p-6 shadow-card dark:border-ink-800 dark:bg-ink-900">
          <h1 className="text-lg font-semibold text-ink-900 dark:text-white">{mode === 'login' ? 'Sign in' : 'Create an account'}</h1>
          <p className="mt-1 text-sm text-ink-500 dark:text-ink-400">Smart Verification — verify before you trust.</p>
          <form onSubmit={submit} className="mt-6 space-y-4">
            <div>
              <label className="field-label" htmlFor="email">Work email</label>
              <input id="email" type="email" required autoComplete="email" className="field" value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
            <div>
              <label className="field-label" htmlFor="password">Password</label>
              <input id="password" type="password" required minLength={8} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} className="field" value={password} onChange={(e) => setPassword(e.target.value)} />
            </div>
            {error && <Alert tone="error">{error}</Alert>}
            {info && <Alert tone="success">{info}</Alert>}
            <Button type="submit" className="w-full" loading={busy}>
              {mode === 'login' ? 'Sign in' : 'Create account'}
            </Button>
          </form>
          <button
            className="mt-4 w-full text-center text-sm text-brand-700 hover:underline dark:text-brand-400"
            onClick={() => setMode(mode === 'login' ? 'signup' : 'login')}
          >
            {mode === 'login' ? 'Need an account? Sign up' : 'Already have an account? Sign in'}
          </button>
        </div>
      </div>
    </div>
  );
}
