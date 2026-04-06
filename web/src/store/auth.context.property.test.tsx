/**
 * Property-Based Tests for Auth Context
 * 
 * Feature: frontend-backend-integration
 * Tests Properties 5 and 19 from the design document
 * 
 * **Validates: Requirements 6.3, 6.6**
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import * as fc from 'fast-check';
import { renderHook, act, waitFor } from '@testing-library/react';
import { AuthProvider, useAuth } from './auth.context';
import AuthService, { type LoginParams, type LoginResult } from '../services/auth.service';
import TokenManager, { type UserInfo } from '../lib/token-manager';
import React from 'react';

// Mock dependencies
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

// ==================== Arbitraries (Generators) ====================

const userTypeArbitrary = fc.constantFrom('teacher' as const, 'student' as const);

const userInfoArbitrary = fc.record({
  id: fc.uuid(),
  name: fc.string({ minLength: 1, maxLength: 50 }),
  email: fc.emailAddress(),
  user_type: userTypeArbitrary,
  avatar: fc.option(fc.webUrl(), { nil: undefined }),
  phone: fc.option(fc.string({ minLength: 10, maxLength: 15 }), { nil: undefined }),
  student_id: fc.option(fc.string({ minLength: 5, maxLength: 20 }), { nil: undefined }),
  created_at: fc.option(fc.date().map(d => d.toISOString()), { nil: undefined }),
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
  expires_in: fc.integer({ min: 300, max: 86400 }),
  user: userInfoArbitrary,
});

const partialUserInfoArbitrary = fc.record({
  name: fc.option(fc.string({ minLength: 1, maxLength: 50 }), { nil: undefined }),
  email: fc.option(fc.emailAddress(), { nil: undefined }),
  avatar: fc.option(fc.webUrl(), { nil: undefined }),
  phone: fc.option(fc.string({ minLength: 10, maxLength: 15 }), { nil: undefined }),
  student_id: fc.option(fc.string({ minLength: 5, maxLength: 20 }), { nil: undefined }),
}, { requiredKeys: [] });

// ==================== Helper Functions ====================

function wrapper({ children }: { children: React.ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>;
}

async function waitForHookInit(result: any) {
  await waitFor(() => {
    expect(result.current).not.toBeNull();
    expect(result.current.loading).toBe(false);
  }, { timeout: 1000 });
}

describe('Auth Context - Property-Based Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    
    vi.mocked(AuthService.isAuthenticated).mockReturnValue(false);
    vi.mocked(AuthService.getCurrentUser).mockReturnValue(null);
    vi.mocked(TokenManager.getUserInfo).mockReturnValue(null);
    vi.mocked(TokenManager.getAccessToken).mockReturnValue(null);
  });

  afterEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  describe('Property 5: State Update on Login', () => {
    /**
     * **Validates: Requirements 6.3**
     * 
     * Property: For any successful login response containing user information,
     * the State_Manager should update the global state with user data and set
     * isAuthenticated to true.
     */
    it('should update state with user data and set isAuthenticated to true for any successful login', async () => {
      await fc.assert(
        fc.asyncProperty(loginParamsArbitrary, loginResultArbitrary, async (loginParams, loginResult) => {
          vi.mocked(AuthService.login).mockResolvedValue(loginResult);

          const { result } = renderHook(() => useAuth(), { wrapper });
          await waitForHookInit(result);
          
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

    it('should preserve all user fields including optional ones after login', async () => {
      await fc.assert(
        fc.asyncProperty(
          loginParamsArbitrary,
          fc.record({
            access_token: fc.string({ minLength: 20, maxLength: 200 }),
            refresh_token: fc.string({ minLength: 20, maxLength: 200 }),
            token_type: fc.constant('Bearer'),
            expires_in: fc.integer({ min: 300, max: 86400 }),
            user: fc.record({
              id: fc.uuid(),
              name: fc.string({ minLength: 1, maxLength: 50 }),
              email: fc.emailAddress(),
              user_type: userTypeArbitrary,
              avatar: fc.webUrl(),
              phone: fc.string({ minLength: 10, maxLength: 15 }),
              student_id: fc.string({ minLength: 5, maxLength: 20 }),
              created_at: fc.date().map(d => d.toISOString()),
            }),
          }),
          async (loginParams, loginResult) => {
            vi.mocked(AuthService.login).mockResolvedValue(loginResult);

            const { result } = renderHook(() => useAuth(), { wrapper });
            await waitForHookInit(result);
            
            await act(async () => {
              await result.current.login(loginParams);
            });

            expect(result.current.user).toEqual(loginResult.user);
            expect(result.current.user?.avatar).toBe(loginResult.user.avatar);
            expect(result.current.user?.phone).toBe(loginResult.user.phone);
            expect(result.current.user?.student_id).toBe(loginResult.user.student_id);
            expect(result.current.user?.created_at).toBe(loginResult.user.created_at);
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should clear state on logout after successful login', async () => {
      await fc.assert(
        fc.asyncProperty(loginParamsArbitrary, loginResultArbitrary, async (loginParams, loginResult) => {
          vi.mocked(AuthService.login).mockResolvedValue(loginResult);

          const { result } = renderHook(() => useAuth(), { wrapper });
          await waitForHookInit(result);
          
          await act(async () => {
            await result.current.login(loginParams);
          });

          expect(result.current.isAuthenticated).toBe(true);
          expect(result.current.user).toEqual(loginResult.user);

          act(() => {
            result.current.logout();
          });

          expect(result.current.isAuthenticated).toBe(false);
          expect(result.current.user).toBeNull();
          expect(result.current.loading).toBe(false);
        }),
        { numRuns: 100 }
      );
    });
  });

  describe('Property 19: State Persistence', () => {
    /**
     * **Validates: Requirements 6.6**
     * 
     * Property: For any user state update in State_Manager, the updated state
     * should be automatically persisted to localStorage.
     */
    it('should persist user info to localStorage when updateUser is called', async () => {
      await fc.assert(
        fc.asyncProperty(
          loginResultArbitrary,
          partialUserInfoArbitrary,
          async (loginResult, partialUpdate) => {
            // Skip if update is empty
            if (Object.keys(partialUpdate).length === 0) {
              return true;
            }

            vi.mocked(AuthService.login).mockResolvedValue(loginResult);

            const { result } = renderHook(() => useAuth(), { wrapper });
            await waitForHookInit(result);
            
            await act(async () => {
              await result.current.login({
                account: 'test@example.com',
                password: 'password123',
                user_type: 'student',
              });
            });

            act(() => {
              result.current.updateUser(partialUpdate);
            });

            expect(TokenManager.setUserInfo).toHaveBeenCalled();
            
            const calls = vi.mocked(TokenManager.setUserInfo).mock.calls;
            const lastCall = calls[calls.length - 1];
            const persistedUser = lastCall[0];

            Object.keys(partialUpdate).forEach((key) => {
              const value = partialUpdate[key as keyof typeof partialUpdate];
              if (value !== undefined) {
                expect(persistedUser[key as keyof UserInfo]).toBe(value);
              }
            });
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should preserve original user fields when updating partial fields', async () => {
      await fc.assert(
        fc.asyncProperty(
          loginResultArbitrary,
          fc.string({ minLength: 1, maxLength: 50 }),
          async (loginResult, newName) => {
            vi.mocked(AuthService.login).mockResolvedValue(loginResult);

            const { result } = renderHook(() => useAuth(), { wrapper });
            await waitForHookInit(result);
            
            await act(async () => {
              await result.current.login({
                account: 'test@example.com',
                password: 'password123',
                user_type: 'student',
              });
            });

            act(() => {
              result.current.updateUser({ name: newName });
            });

            expect(result.current.user?.id).toBe(loginResult.user.id);
            expect(result.current.user?.email).toBe(loginResult.user.email);
            expect(result.current.user?.user_type).toBe(loginResult.user.user_type);
            expect(result.current.user?.name).toBe(newName);

            const calls = vi.mocked(TokenManager.setUserInfo).mock.calls;
            const lastCall = calls[calls.length - 1];
            const persistedUser = lastCall[0];
            
            expect(persistedUser.id).toBe(loginResult.user.id);
            expect(persistedUser.email).toBe(loginResult.user.email);
            expect(persistedUser.user_type).toBe(loginResult.user.user_type);
            expect(persistedUser.name).toBe(newName);
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should not persist when updateUser is called without a logged-in user', async () => {
      await fc.assert(
        fc.asyncProperty(partialUserInfoArbitrary, async (partialUpdate) => {
          vi.mocked(AuthService.isAuthenticated).mockReturnValue(false);
          vi.mocked(AuthService.getCurrentUser).mockReturnValue(null);

          const { result } = renderHook(() => useAuth(), { wrapper });
          await waitForHookInit(result);

          vi.mocked(TokenManager.setUserInfo).mockClear();

          act(() => {
            result.current.updateUser(partialUpdate);
          });

          expect(TokenManager.setUserInfo).not.toHaveBeenCalled();
          expect(result.current.user).toBeNull();
        }),
        { numRuns: 100 }
      );
    });

    it('should restore persisted state on initialization', async () => {
      await fc.assert(
        fc.asyncProperty(userInfoArbitrary, async (userInfo) => {
          vi.mocked(AuthService.isAuthenticated).mockReturnValue(true);
          vi.mocked(AuthService.getCurrentUser).mockReturnValue(userInfo);
          vi.mocked(TokenManager.getUserInfo).mockReturnValue(userInfo);
          vi.mocked(TokenManager.getAccessToken).mockReturnValue('mock-token');

          const { result } = renderHook(() => useAuth(), { wrapper });
          await waitForHookInit(result);

          expect(result.current.isAuthenticated).toBe(true);
          expect(result.current.user).toEqual(userInfo);
        }),
        { numRuns: 100 }
      );
    });
  });
});
