import { useCallback, useEffect, useState } from 'react';
import { api, ApiError } from './api';

/** Fetches `path` on mount (and when it changes). Exposes data, error, loading and reload. */
export function useApi<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(Boolean(path));

  const load = useCallback(async () => {
    if (!path) return;
    setLoading(true);
    setError(null);
    try {
      setData(await api<T>(path));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load data.');
    } finally {
      setLoading(false);
    }
  }, [path]);

  useEffect(() => {
    void load();
  }, [load]);

  return { data, setData, error, loading, reload: load };
}
