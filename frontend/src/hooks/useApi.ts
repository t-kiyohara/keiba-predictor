import { useState, useCallback, useRef } from 'react';

const API_BASE = '/api';

export function useApi() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const loadingCount = useRef(0);

  const fetchApi = useCallback(async <T>(path: string, options?: RequestInit): Promise<T | null> => {
    loadingCount.current += 1;
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}${path}`, {
        headers: { 'Content-Type': 'application/json' },
        ...options,
      });
      if (!response.ok) {
        throw new Error(`API Error: ${response.status} ${response.statusText}`);
      }
      const data = await response.json();
      return data as T;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error';
      setError(message);
      return null;
    } finally {
      loadingCount.current -= 1;
      if (loadingCount.current === 0) {
        setLoading(false);
      }
    }
  }, []);

  return { fetchApi, loading, error };
}
