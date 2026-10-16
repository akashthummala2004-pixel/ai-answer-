import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { api, ApiError, loadSession, saveSession, type Session } from '../lib/api';
import type { Health } from '../lib/types';

interface AppState {
  health: Health | null;
  healthError: string | null;
  session: Session | null;
  retryHealth: () => void;
  signIn: (email: string, password: string, mode: 'login' | 'signup') => Promise<string | null>;
  signOut: () => void;
}

const AppContext = createContext<AppState | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [session, setSession] = useState<Session | null>(loadSession);

  const retryHealth = useCallback(() => {
    setHealthError(null);
    api<Health>('/api/health', { timeoutMs: 8000 })
      .then(setHealth)
      .catch((err: ApiError) => setHealthError(err.message));
  }, []);

  useEffect(retryHealth, [retryHealth]);

  useEffect(() => {
    const onSession = (e: Event) => setSession((e as CustomEvent<Session | null>).detail);
    window.addEventListener('mm-session', onSession);
    return () => window.removeEventListener('mm-session', onSession);
  }, []);

  const signIn = useCallback(async (email: string, password: string, mode: 'login' | 'signup') => {
    const data = await api<{ access_token: string | null; refresh_token?: string; message?: string; user?: { email: string } }>(
      `/api/auth/${mode}`,
      { method: 'POST', body: { email, password } },
    );
    if (!data.access_token) return data.message ?? 'Check your email to confirm your account.';
    saveSession({ access_token: data.access_token, refresh_token: data.refresh_token ?? null, email: data.user?.email ?? email });
    return null;
  }, []);

  const signOut = useCallback(() => {
    // Revoke the server-side session first; clear locally whatever happens.
    api('/api/auth/logout', { method: 'POST', timeoutMs: 8000 })
      .catch(() => undefined)
      .finally(() => saveSession(null));
  }, []);

  return (
    <AppContext.Provider value={{ health, healthError, session, retryHealth, signIn, signOut }}>{children}</AppContext.Provider>
  );
}

export function useApp(): AppState {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp must be used inside AppProvider');
  return ctx;
}
