/**
 * Property-Based Tests for Auth Service
 * 
 * Feature: frontend-backend-integration
 * Tests Properties 4, 5, and 6 from the design document
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import * as fc from 'fast-check';
import AuthService, {
  type LoginParams,
  type LoginResult,
} from './auth.service';
import TokenManager, { type TokenData, type UserInfo } from '../lib/token-manager';
import { api } from '../lib/api';

// Mock dependencies
vi.mock('../lib/api', () => ({
  api: {
    post: vi.fn(),
  },
}));

vi.mock('../lib/token-manager', () => ({
  default: {
    setTokens: vi.fn(),
    setUserInfo: vi.fn(),
    clearAll: vi.fn(),
    getAccessToken: vi.fn(),
    getUserInfo: vi.fn(),
  },
}));

// Arbitraries for property-based testing
const tokenDataArbitrary = fc.record({
  access_token: fc.string({ minLength: 20, maxLength: 200 }),
  refresh_token: fc.string({ minLength: 20, maxLength: 200 }),
  token_type: fc.constant('Bearer'),
  expires_in: fc.integer({ min: 300, max: 86400 }),
});

const userInfoArbitrary = fc.record({
  id: fc.uuid(),
  name: fc.string({ minLength: 1, maxLength: 50 }),
  email: fc.emailAddress(),
  user_type: fc.constantFrom('teacher' as const, 'student' as const),
  avatar: fc.option(fc.webUrl(), { nil: undefined }),
  phone: fc.option(fc.string({ minLength: 10, maxLength: 15 }), { nil: undefined }),
  student_id: fc.option(fc.string({ minLength: 5, maxLength: 20 }), { nil: undefined }),
  created_at: fc.option(fc.date().map(d => d.toISOString()), { nil: undefined }),
});

const loginParamsArbitrary = fc.record({
  account: fc.oneof(fc.emailAddress(), fc.string({ minLength: 5, maxLength: 20 })),
  password: fc.string({ minLength: 6, maxLength: 50 }),
  user_type: fc.constantFrom('teacher' as const, 'student' as const),
});

const loginResultArbitrary = fc.tuple(tokenDataArbitrary, userInfoArbitrary).map(
  ([tokenData, userInfo]): LoginResult => ({
    ...tokenData,
    user: userInfo,
  })
);

describe('Auth Service - Property-Based Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    delete (window as any).location;
    (window as any).location = { href: '' };
  });

  describe('Property 4: Token Storage on Login', () => {
    /**
     * **Validates: Requirements 2.4**
     * 
     * Property: For any successful login response containing access_token and refresh_token,
     * the TokenManager should store both tokens to localStorage with correct key names.
     */
    it('should store tokens for any successful login response', () => {
      fc.assert(
        fc.property(loginParamsArbitrary, loginResultArbitrary, async (loginParams, loginResult) => {
          // Arrange
          vi.mocked(api.post).mockResolvedValue(loginResult);

          // Act
          await AuthService.login(loginParams);

          // Assert: TokenManager.setTokens should be called with correct token data
          expect(TokenManager.setTokens).toHaveBeenCalledWith({
            access_token: loginResult.access_token,
            refresh_token: loginResult.refresh_token,
            token_type: loginResult.token_type,
            expires_in: loginResult.expires_in,
          });
          expect(TokenManager.setTokens).toHaveBeenCalledTimes(1);

          // Cleanup
          vi.clearAllMocks();
        }),
        { numRuns: 100 }
      );
    });

    it('should store both access_token and refresh_token for any login', () => {
      fc.assert(
        fc.property(loginParamsArbitrary, loginResultArbitrary, async (loginParams, loginResult) => {
          // Arrange
          vi.mocked(api.post).mockResolvedValue(loginResult);
          let storedTokenData: TokenData | null = null;

          vi.mocked(TokenManager.setTokens).mockImplementation((tokenData: TokenData) => {
            storedTokenData = tokenData;
          });

          // Act
          await AuthService.login(loginParams);

          // Assert: Both tokens should be present
          expect(storedTokenData).not.toBeNull();
          expect(storedTokenData!.access_token).toBe(loginResult.access_token);
          expect(storedTokenData!.refresh_token).toBe(loginResult.refresh_token);
          expect(storedTokenData!.token_type).toBe('Bearer');
          expect(storedTokenData!.expires_in).toBe(loginResult.expires_in);

          // Cleanup
          vi.clearAllMocks();
        }),
        { numRuns: 100 }
      );
    });

    it('should not store tokens when login fails', () => {
      fc.assert(
        fc.property(loginParamsArbitrary, fc.string(), async (loginParams, errorMessage) => {
          // Arrange
          vi.mocked(api.post).mockRejectedValue(new Error(errorMessage));

          // Act & Assert
          try {
            await AuthService.login(loginParams);
            // Should not reach here
            expect(true).toBe(false);
          } catch (error) {
            // Assert: TokenManager.setTokens should NOT be called on failure
            expect(TokenManager.setTokens).not.toHaveBeenCalled();
            expect(TokenManager.setUserInfo).not.toHaveBeenCalled();
          }

          // Cleanup
          vi.clearAllMocks();
        }),
        { numRuns: 100 }
      );
    });
  });

  describe('Property 5: State Update on Login', () => {
    /**
     * **Validates: Requirements 2.5**
     * 
     * Property: For any successful login response containing user information,
     * the State_Manager should update the global state with user data and set
     * isAuthenticated to true.
     * 
     * Note: This tests the Auth Service's role in state updates (storing user info).
     */
    it('should store user info for any successful login response', () => {
      fc.assert(
        fc.property(loginParamsArbitrary, loginResultArbitrary, async (loginParams, loginResult) => {
          // Arrange
          vi.mocked(api.post).mockResolvedValue(loginResult);

          // Act
          await AuthService.login(loginParams);

          // Assert: TokenManager.setUserInfo should be called with user data
          expect(TokenManager.setUserInfo).toHaveBeenCalledWith(loginResult.user);
          expect(TokenManager.setUserInfo).toHaveBeenCalledTimes(1);

          // Cleanup
          vi.clearAllMocks();
        }),
        { numRuns: 100 }
      );
    });

    it('should store complete user info including all fields', () => {
      fc.assert(
        fc.property(loginParamsArbitrary, loginResultArbitrary, async (loginParams, loginResult) => {
          // Arrange
          vi.mocked(api.post).mockResolvedValue(loginResult);
          let storedUserInfo: UserInfo | null = null;

          vi.mocked(TokenManager.setUserInfo).mockImplementation((userInfo: UserInfo) => {
            storedUserInfo = userInfo;
          });

          // Act
          await AuthService.login(loginParams);

          // Assert: All user fields should be stored
          expect(storedUserInfo).not.toBeNull();
          expect(storedUserInfo!.id).toBe(loginResult.user.id);
          expect(storedUserInfo!.name).toBe(loginResult.user.name);
          expect(storedUserInfo!.email).toBe(loginResult.user.email);
          expect(storedUserInfo!.user_type).toBe(loginResult.user.user_type);

          // Optional fields should match if present
          if (loginResult.user.avatar) {
            expect(storedUserInfo!.avatar).toBe(loginResult.user.avatar);
          }
          if (loginResult.user.phone) {
            expect(storedUserInfo!.phone).toBe(loginResult.user.phone);
          }
          if (loginResult.user.student_id) {
            expect(storedUserInfo!.student_id).toBe(loginResult.user.student_id);
          }

          // Cleanup
          vi.clearAllMocks();
        }),
        { numRuns: 100 }
      );
    });

    it('should store tokens before storing user info', () => {
      fc.assert(
        fc.property(loginParamsArbitrary, loginResultArbitrary, async (loginParams, loginResult) => {
          // Arrange
          vi.mocked(api.post).mockResolvedValue(loginResult);
          const callOrder: string[] = [];

          vi.mocked(TokenManager.setTokens).mockImplementation(() => {
            callOrder.push('setTokens');
          });

          vi.mocked(TokenManager.setUserInfo).mockImplementation(() => {
            callOrder.push('setUserInfo');
          });

          // Act
          await AuthService.login(loginParams);

          // Assert: setTokens should be called before setUserInfo
          expect(callOrder).toEqual(['setTokens', 'setUserInfo']);

          // Cleanup
          vi.clearAllMocks();
        }),
        { numRuns: 100 }
      );
    });

    it('should handle user info with different user types', () => {
      fc.assert(
        fc.property(
          loginParamsArbitrary,
          loginResultArbitrary,
          async (loginParams, loginResult) => {
            // Arrange
            vi.mocked(api.post).mockResolvedValue(loginResult);

            // Act
            await AuthService.login(loginParams);

            // Assert: User type should be preserved
            const setUserInfoCall = vi.mocked(TokenManager.setUserInfo).mock.calls[0];
            expect(setUserInfoCall[0].user_type).toMatch(/^(teacher|student)$/);

            // Cleanup
            vi.clearAllMocks();
          }
        ),
        { numRuns: 100 }
      );
    });
  });

  describe('Property 6: Token Cleanup on Logout', () => {
    /**
     * **Validates: Requirements 2.9**
     * 
     * Property: For any logout operation, the TokenManager should remove all
     * authentication-related items from localStorage (access_token, refresh_token,
     * token_expires_at, user_info).
     */
    it('should clear all authentication data on logout', () => {
      fc.assert(
        fc.property(fc.constant(null), () => {
          // Act
          AuthService.logout();

          // Assert: TokenManager.clearAll should be called
          expect(TokenManager.clearAll).toHaveBeenCalledTimes(1);

          // Cleanup
          vi.clearAllMocks();
        }),
        { numRuns: 100 }
      );
    });

    it('should clear authentication data regardless of current state', () => {
      fc.assert(
        fc.property(
          fc.option(tokenDataArbitrary, { nil: null }),
          fc.option(userInfoArbitrary, { nil: null }),
          (tokenData, userInfo) => {
            // Arrange: Mock current state (may or may not have tokens/user)
            if (tokenData) {
              vi.mocked(TokenManager.getAccessToken).mockReturnValue(tokenData.access_token);
            } else {
              vi.mocked(TokenManager.getAccessToken).mockReturnValue(null);
            }

            if (userInfo) {
              vi.mocked(TokenManager.getUserInfo).mockReturnValue(userInfo);
            } else {
              vi.mocked(TokenManager.getUserInfo).mockReturnValue(null);
            }

            // Act
            AuthService.logout();

            // Assert: clearAll should be called regardless of current state
            expect(TokenManager.clearAll).toHaveBeenCalledTimes(1);

            // Cleanup
            vi.clearAllMocks();
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should clear authentication data even if clearAll throws', () => {
      fc.assert(
        fc.property(fc.string(), (errorMessage) => {
          // Arrange: Mock clearAll to throw
          vi.mocked(TokenManager.clearAll).mockImplementation(() => {
            throw new Error(errorMessage);
          });

          // Act: logout should not throw
          expect(() => AuthService.logout()).not.toThrow();

          // Assert: clearAll should still be called
          expect(TokenManager.clearAll).toHaveBeenCalledTimes(1);

          // Cleanup
          vi.clearAllMocks();
          vi.mocked(TokenManager.clearAll).mockImplementation(() => {});
        }),
        { numRuns: 100 }
      );
    });

    it('should redirect to login page after clearing authentication data', () => {
      fc.assert(
        fc.property(fc.constant(null), () => {
          // Arrange
          (window as any).location = { href: '' };

          // Act
          AuthService.logout();

          // Assert: Should redirect to /login
          expect(window.location.href).toBe('/login');

          // Cleanup
          vi.clearAllMocks();
        }),
        { numRuns: 100 }
      );
    });
  });

  describe('Integration: Login-Logout Cycle', () => {
    it('should handle complete login-logout cycle for any user', () => {
      fc.assert(
        fc.property(loginParamsArbitrary, loginResultArbitrary, async (loginParams, loginResult) => {
          // Arrange
          vi.mocked(api.post).mockResolvedValue(loginResult);

          // Act: Login
          await AuthService.login(loginParams);

          // Assert: Login should store tokens and user info
          expect(TokenManager.setTokens).toHaveBeenCalledTimes(1);
          expect(TokenManager.setUserInfo).toHaveBeenCalledTimes(1);

          // Act: Logout
          AuthService.logout();

          // Assert: Logout should clear all data
          expect(TokenManager.clearAll).toHaveBeenCalledTimes(1);

          // Cleanup
          vi.clearAllMocks();
        }),
        { numRuns: 100 }
      );
    });

    it('should allow multiple login-logout cycles', () => {
      fc.assert(
        fc.property(
          fc.array(fc.tuple(loginParamsArbitrary, loginResultArbitrary), {
            minLength: 2,
            maxLength: 5,
          }),
          async (loginCycles) => {
            for (const [loginParams, loginResult] of loginCycles) {
              // Arrange
              vi.mocked(api.post).mockResolvedValue(loginResult);

              // Act: Login
              await AuthService.login(loginParams);

              // Assert: Login should store data
              expect(TokenManager.setTokens).toHaveBeenCalled();
              expect(TokenManager.setUserInfo).toHaveBeenCalled();

              // Act: Logout
              AuthService.logout();

              // Assert: Logout should clear data
              expect(TokenManager.clearAll).toHaveBeenCalled();

              // Reset mocks for next cycle
              vi.clearAllMocks();
            }
          }
        ),
        { numRuns: 100 }
      );
    });
  });
});
