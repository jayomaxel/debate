import axios from 'axios';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import TokenManager from './token-manager';

vi.mock('axios');

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

  it('stores token bundle in localStorage', () => {
    TokenManager.setTokens({
      access_token: 'access-1',
      refresh_token: 'refresh-1',
      expires_in: 3600,
    });

    expect(localStorage.getItem('access_token')).toBe('access-1');
    expect(localStorage.getItem('refresh_token')).toBe('refresh-1');
    expect(localStorage.getItem('token_type')).toBe('bearer');
    expect(Number(localStorage.getItem('token_expires_at'))).toBe(Date.now() + 3600 * 1000);
  });

  it('refreshes tokens using the refresh token and updates local state', async () => {
    TokenManager.setTokens({
      access_token: 'access-1',
      refresh_token: 'refresh-1',
      expires_in: 3600,
    });
    TokenManager.setUserInfo({
      id: 'user-1',
      account: 'student-1',
      name: 'Student One',
      user_type: 'student',
    });

    vi.mocked(axios.post).mockResolvedValue({
      data: {
        data: {
          access_token: 'access-2',
          refresh_token: 'refresh-2',
          token_type: 'Bearer',
          expires_in: 7200,
          user: {
            id: 'user-1',
            account: 'student-1',
            name: 'Student Updated',
            user_type: 'student',
          },
        },
      },
    });

    const result = await TokenManager.refreshToken();

    expect(axios.post).toHaveBeenCalledTimes(1);
    expect(localStorage.getItem('access_token')).toBe('access-2');
    expect(localStorage.getItem('refresh_token')).toBe('refresh-2');
    expect(TokenManager.getUserInfo()?.name).toBe('Student Updated');
    expect(result.access_token).toBe('access-2');
  });
});
