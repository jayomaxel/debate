import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import * as fc from 'fast-check';
import React from 'react';
import { act, renderHook, waitFor } from '@testing-library/react';
import { AuthProvider, useAuth } from './auth.context';
import AuthService from '../services/auth.service';
import TokenManager from '../lib/token-manager';

vi.mock('../services/auth.service', () => ({
  default: {
    login: vi.fn(),
    logout: vi.fn(),
    isAuthenticated: vi.fn(),
    getCurrentUser: vi.fn(),
  },
}));

vi.mock('../lib/token-manager', () => ({
  default: {
    setUserInfo: vi.fn(),
    getUserInfo: vi.fn(),
    getAccessToken: vi.fn(),
    clearAll: vi.fn(),
  },
}));

const isoDateArbitrary = fc
  .integer({
    min: Date.parse('2000-01-01T00:00:00.000Z'),
    max: Date.parse('2100-12-31T23:59:59.999Z'),
  })
  .map((timestamp) => new Date(timestamp).toISOString());
const userTypeArbitrary = fc.constantFrom('teacher' as const, 'student' as const, 'administrator' as const);

const userInfoArbitrary = fc.record({
  id: fc.uuid(),
  account: fc.oneof(fc.emailAddress(), fc.string({ minLength: 5, maxLength: 20 })),
  name: fc.string({ minLength: 1, maxLength: 50 }),
  email: fc.emailAddress(),
  user_type: userTypeArbitrary,
  avatar: fc.option(fc.webUrl(), { nil: undefined }),
  phone: fc.option(fc.string({ minLength: 10, maxLength: 15 }), { nil: undefined }),
  student_id: fc.option(fc.string({ minLength: 5, maxLength: 20 }), { nil: undefined }),
  class_id: fc.option(fc.string({ minLength: 4, maxLength: 20 }), { nil: undefined }),
  created_at: fc.option(isoDateArbitrary, { nil: undefined }),
});

const loginParamsArbitrary = fc.record({
  account: fc.oneof(fc.emailAddress(), fc.string({ minLength: 5, maxLength: 20 })),
  password: fc.string({ minLength: 6, maxLength: 50 }),
  user_type: userTypeArbitrary,
});

const loginResultArbitrary = fc.record({
  access_token: fc.string({ minLength: 20, maxLength: 200 }),
  refresh_token: fc.string({ minLength: 20, maxLength: 200 }),
  token_type: fc.constant('Bearer'),
  expires_in: fc.integer({ min: 300, max: 86_400 }),
  user: userInfoArbitrary,
});

const partialUserInfoArbitrary = fc.record(
  {
    account: fc.option(fc.oneof(fc.emailAddress(), fc.string({ minLength: 5, maxLength: 20 })), {
      nil: undefined,
    }),
    name: fc.option(fc.string({ minLength: 1, maxLength: 50 }), { nil: undefined }),
    email: fc.option(fc.emailAddress(), { nil: undefined }),
    avatar: fc.option(fc.webUrl(), { nil: undefined }),
    phone: fc.option(fc.string({ minLength: 10, maxLength: 15 }), { nil: undefined }),
    student_id: fc.option(fc.string({ minLength: 5, maxLength: 20 }), { nil: undefined }),
    class_id: fc.option(fc.string({ minLength: 4, maxLength: 20 }), { nil: undefined }),
    created_at: fc.option(isoDateArbitrary, { nil: undefined }),
  },
  { requiredKeys: [] }
);

function wrapper({ children }: { children: React.ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>;
}

async function waitForHookReady(result: ReturnType<typeof renderHook<typeof useAuth>>['result']) {
  await waitFor(() => {
    expect(result.current.loading).toBe(false);
  });
}

describe('Auth Context - Property-Based Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(AuthService.isAuthenticated).mockReturnValue(false);
    vi.mocked(AuthService.getCurrentUser).mockReturnValue(null);
    vi.mocked(TokenManager.getUserInfo).mockReturnValue(null);
    vi.mocked(TokenManager.getAccessToken).mockReturnValue(null);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('marks the user authenticated and stores the returned user after login', async () => {
    await fc.assert(
      fc.asyncProperty(loginParamsArbitrary, loginResultArbitrary, async (loginParams, loginResult) => {
        vi.mocked(AuthService.login).mockResolvedValue(loginResult);

        const { result } = renderHook(() => useAuth(), { wrapper });
        await waitForHookReady(result);

        await act(async () => {
          await result.current.login(loginParams);
        });

        expect(result.current.isAuthenticated).toBe(true);
        expect(result.current.user).toEqual(loginResult.user);
        expect(result.current.loading).toBe(false);
      }),
      { numRuns: 100 }
    );
  });

  it('merges partial user updates into the existing user and persists them', async () => {
    await fc.assert(
      fc.asyncProperty(loginResultArbitrary, partialUserInfoArbitrary, async (loginResult, partialUpdate) => {
        vi.mocked(AuthService.login).mockResolvedValue(loginResult);

        const { result } = renderHook(() => useAuth(), { wrapper });
        await waitForHookReady(result);

        await act(async () => {
          await result.current.login({
            account: 'account@example.com',
            password: 'password123',
            user_type: loginResult.user.user_type,
          });
        });

        const expectedUser = {
          ...loginResult.user,
          ...partialUpdate,
        };

        act(() => {
          result.current.updateUser(partialUpdate);
        });

        expect(result.current.user).toEqual(expectedUser);
        expect(TokenManager.setUserInfo).toHaveBeenLastCalledWith(expectedUser);
      }),
      { numRuns: 100 }
    );
  });

  it('does nothing when updateUser is called without a logged-in user', async () => {
    await fc.assert(
      fc.asyncProperty(partialUserInfoArbitrary, async (partialUpdate) => {
        vi.mocked(AuthService.isAuthenticated).mockReturnValue(false);
        vi.mocked(AuthService.getCurrentUser).mockReturnValue(null);

        const { result } = renderHook(() => useAuth(), { wrapper });
        await waitForHookReady(result);
        vi.mocked(TokenManager.setUserInfo).mockClear();

        act(() => {
          result.current.updateUser(partialUpdate);
        });

        expect(result.current.user).toBeNull();
        expect(TokenManager.setUserInfo).not.toHaveBeenCalled();
      }),
      { numRuns: 100 }
    );
  });

  it('restores the persisted authenticated state on initialization', async () => {
    await fc.assert(
      fc.asyncProperty(userInfoArbitrary, async (userInfo) => {
        vi.mocked(AuthService.isAuthenticated).mockReturnValue(true);
        vi.mocked(AuthService.getCurrentUser).mockReturnValue(userInfo);
        vi.mocked(TokenManager.getUserInfo).mockReturnValue(userInfo);
        vi.mocked(TokenManager.getAccessToken).mockReturnValue('mock-token');

        const { result } = renderHook(() => useAuth(), { wrapper });
        await waitForHookReady(result);

        expect(result.current.isAuthenticated).toBe(true);
        expect(result.current.user).toEqual(userInfo);
      }),
      { numRuns: 100 }
    );
  });
});
