import { useState, useCallback } from 'react';

interface UseApiResult<T> {
  loading: boolean;
  error: string | null;
  data: T | null;
  execute: () => Promise<T | null>;
}

export function useApi<T>(fetcher: () => Promise<T>): UseApiResult<T> {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<T | null>(null);

  const execute = useCallback(async (): Promise<T | null> => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetcher();
      setData(result);
      setLoading(false);
      return result;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'An unknown error occurred';
      setError(message);
      setLoading(false);
      return null;
    }
  }, [fetcher]);

  return { loading, error, data, execute };
}
