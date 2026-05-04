import { renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { usePageActivityRefresh } from './use-page-activity-refresh';

describe('usePageActivityRefresh', () => {
  let visibilityState = 'visible';

  beforeEach(() => {
    vi.useFakeTimers();
    visibilityState = 'visible';

    Object.defineProperty(document, 'visibilityState', {
      configurable: true,
      get: () => visibilityState,
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('refreshes on focus and while visible at the configured interval', () => {
    const refresh = vi.fn();
    renderHook(() =>
      usePageActivityRefresh(refresh, { enabled: true, intervalMs: 1000 })
    );

    window.dispatchEvent(new Event('focus'));
    expect(refresh).toHaveBeenCalledTimes(1);

    vi.advanceTimersByTime(1000);
    expect(refresh).toHaveBeenCalledTimes(2);
  });

  it('pauses interval refresh when hidden and resumes with an immediate pull when visible again', () => {
    const refresh = vi.fn();
    renderHook(() =>
      usePageActivityRefresh(refresh, { enabled: true, intervalMs: 1000 })
    );

    visibilityState = 'hidden';
    document.dispatchEvent(new Event('visibilitychange'));
    vi.advanceTimersByTime(3000);
    expect(refresh).toHaveBeenCalledTimes(0);

    visibilityState = 'visible';
    document.dispatchEvent(new Event('visibilitychange'));
    expect(refresh).toHaveBeenCalledTimes(1);

    vi.advanceTimersByTime(1000);
    expect(refresh).toHaveBeenCalledTimes(2);
  });
});
