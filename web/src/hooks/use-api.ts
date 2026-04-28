/**
 * useApi Hook
 * 简化API调用的自定义Hook，管理loading、error、data状态
 */

import { useState, useCallback, useEffect } from 'react';

export interface UseApiOptions<T> {
  onSuccess?: (data: T) => void;
  onError?: (error: Error) => void;
  immediate?: boolean;
}

export interface UseApiResult<T> {
  data: T | null;
  loading: boolean;
  error: Error | null;
  execute: () => Promise<void>;
  reset: () => void;
}

/**
 * useApi Hook
 * @param apiCall - API调用函数
 * @param options - 配置选项
 */
export function useApi<T>(
  apiCall: () => Promise<T>,
  options?: UseApiOptions<T>
): UseApiResult<T> {
  const { onSuccess, onError, immediate = false } = options || {};

  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<Error | null>(null);

  const execute = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const result = await apiCall();
      setData(result);

      if (onSuccess) {
        onSuccess(result);
      }
    } catch (err) {
      const error = err as Error;
      setError(error);

      if (onError) {
        onError(error);
      }
    } finally {
      setLoading(false);
    }
  }, [apiCall, onSuccess, onError]);

  const reset = useCallback(() => {
    setData(null);
    setError(null);
    setLoading(false);
  }, []);

  useEffect(() => {
    if (immediate) {
      execute();
    }
  }, [immediate, execute]);

  return {
    data,
    loading,
    error,
    execute,
    reset,
  };
}

export default useApi;
