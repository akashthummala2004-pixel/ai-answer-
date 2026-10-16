// Thin fetch wrapper: timeouts, readable errors, bearer auth and one-shot token refresh.

const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, '') ?? '';
const SESSION_KEY = 'mm-av-session';

export interface Session {
  access_token: string;
  refresh_token: string | null;
  email: string | null;
}

export class ApiError extends Error {
  constructor(message: string, public status: number, public kind?: string) {
    super(message);
  }
}

export function loadSession(): Session | null {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    return raw ? (JSON.parse(raw) as Session) : null;
  } catch {
    return null;
  }
}

export function saveSession(session: Session | null) {
  try {
    if (session) localStorage.setItem(SESSION_KEY, JSON.stringify(session));
    else localStorage.removeItem(SESSION_KEY);
  } catch {
    /* storage unavailable: session lives only in memory for this tab */
  }
  window.dispatchEvent(new CustomEvent('mm-session', { detail: session }));
}

export function formatErrorDetail(detail: unknown): string {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d: { loc?: (string | number)[]; msg?: string }) => {
        const field = (d.loc ?? []).filter((p) => p !== 'body').join(' › ');
        return field ? `${field}: ${d.msg}` : d.msg;
      })
      .join('; ');
  }
  return 'Unexpected error.';
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  /** multipart upload; the browser sets the Content-Type boundary itself */
  form?: FormData;
  timeoutMs?: number;
}

async function rawRequest(path: string, opts: RequestOptions, token: string | null): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), opts.timeoutMs ?? 30_000);
  try {
    return await fetch(`${BASE}${path}`, {
      method: opts.method ?? 'GET',
      headers: {
        ...(opts.body !== undefined ? { 'Content-Type': 'application/json' } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: opts.form ?? (opts.body !== undefined ? JSON.stringify(opts.body) : undefined),
      signal: controller.signal,
    });
  } catch (err) {
    if ((err as Error).name === 'AbortError') throw new ApiError('The request timed out. Please try again.', 0, 'timeout');
    throw new ApiError('Cannot reach the verification service. Check your connection and try again.', 0, 'network');
  } finally {
    clearTimeout(timer);
  }
}

async function tryRefresh(session: Session): Promise<Session | null> {
  if (!session.refresh_token) return null;
  const res = await rawRequest('/api/auth/refresh', { method: 'POST', body: { refresh_token: session.refresh_token } }, null);
  if (!res.ok) return null;
  const data = await res.json();
  const next = { access_token: data.access_token, refresh_token: data.refresh_token, email: session.email };
  saveSession(next);
  return next;
}

async function request(path: string, opts: RequestOptions = {}): Promise<Response> {
  let session = loadSession();
  let res = await rawRequest(path, opts, session?.access_token ?? null);
  if (res.status === 401 && session) {
    session = await tryRefresh(session);
    if (session) res = await rawRequest(path, opts, session.access_token);
    else saveSession(null);
  }
  if (!res.ok) {
    let message = `Request failed (HTTP ${res.status}).`;
    let kind: string | undefined;
    try {
      const data = await res.json();
      message = formatErrorDetail(data.detail);
      kind = data.kind;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(message, res.status, kind);
  }
  return res;
}

export async function api<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const res = await request(path, opts);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export async function downloadFile(path: string, filename: string) {
  const res = await request(path);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
