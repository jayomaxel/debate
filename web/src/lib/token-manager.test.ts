import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import TokenManager from './token-manager';

describe('TokenManager', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-05-03T00:00:00.000Z'));
  });

  afterEach(() => {
    vi.useRealTimers();
    localStorage.clear();
  });

  it('persists session_started_at on first token write and keeps it on later refreshes', () => {
    TokenManager.setTokens({
      access_token: 'access-1',
      refresh_token: 'refresh-1',
      expires_in: 3600,
    });

    const startedAt = TokenManager.getSessionStartedAt();
    expect(startedAt).toBe(Date.now());

    vi.advanceTimersByTime(60_000);

    TokenManager.setTokens({
      access_token: 'access-2',
      refresh_token: 'refresh-2',
      expires_in: 3600,
    });

    expect(TokenManager.getSessionStartedAt()).toBe(startedAt);
  });

  it('expires the session after 24 hours', () => {
    TokenManager.setTokens({
      access_token: 'access-1',
      refresh_token: 'refresh-1',
      expires_in: 3600,
    });

    vi.advanceTimersByTime(24 * 60 * 60 * 1000 - 1);
    expect(TokenManager.isSessionExpired()).toBe(false);

    vi.advanceTimersByTime(1);
    expect(TokenManager.isSessionExpired()).toBe(true);
  });
});
