import { useEffect, useRef } from 'react';

interface UsePageActivityRefreshOptions {
  enabled?: boolean;
  intervalMs?: number;
}

const isPromiseLike = (
  value: void | Promise<void>
): value is Promise<void> =>
  !!value && typeof (value as Promise<void>).then === 'function';

export function usePageActivityRefresh(
  refresh: () => void | Promise<void>,
  options: UsePageActivityRefreshOptions = {}
) {
  const { enabled = true, intervalMs } = options;
  const refreshRef = useRef(refresh);
  const isRefreshingRef = useRef(false);

  useEffect(() => {
    refreshRef.current = refresh;
  }, [refresh]);

  useEffect(() => {
    if (!enabled || typeof window === 'undefined') {
      return;
    }

    let intervalId: number | null = null;

    const runRefresh = () => {
      if (isRefreshingRef.current) {
        return;
      }

      const result = refreshRef.current();

      if (!isPromiseLike(result)) {
        return;
      }

      isRefreshingRef.current = true;
      void result.finally(() => {
        isRefreshingRef.current = false;
      });
    };

    const refreshIfVisible = () => {
      if (document.visibilityState === 'visible') {
        runRefresh();
      }
    };

    const stopInterval = () => {
      if (intervalId === null) {
        return;
      }

      window.clearInterval(intervalId);
      intervalId = null;
    };

    const startInterval = () => {
      if (
        !intervalMs ||
        intervalMs <= 0 ||
        document.visibilityState !== 'visible' ||
        intervalId !== null
      ) {
        return;
      }

      intervalId = window.setInterval(refreshIfVisible, intervalMs);
    };

    const handleFocus = () => {
      refreshIfVisible();
    };

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        refreshIfVisible();
        startInterval();
        return;
      }

      stopInterval();
    };

    window.addEventListener('focus', handleFocus);
    document.addEventListener('visibilitychange', handleVisibilityChange);
    startInterval();

    return () => {
      stopInterval();
      window.removeEventListener('focus', handleFocus);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [enabled, intervalMs]);
}
