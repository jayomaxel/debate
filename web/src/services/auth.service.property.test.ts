/**
 * Property-Based Tests for Auth Service
 * 
 * Feature: frontend-backend-integration
 * Tests Properties 4, 5, and 6 from the design document
 * 
 * **Validates: Requirements 2.4, 2.5, 2.9**
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import * as fc from 'fast-check';
import AuthService, { type LoginParams, type LoginResult } from './auth.service';
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
    isTokenExpired: vi.fn(),
    refreshToken: vi.fn(),
  },
}));

// ==================== Arbitraries (Generators) ====================

/**
 * Generator for valid access tokens
 */
const accessTokenArbitrary = fc.string({ minLength: 20, maxLength: 200 });

/**
 * Generator for valid refresh tokens
 */
const refreshTokenArbitrary = fc.string({ minLength: 20, maxLength: 200 });

/**
 * Generator for token expiration time (in seconds)
 */
const expiresInArbitrary = fc.integer({ min: 300, max: 86400 }); // 5 minutes to 24 hours

/**
 * Generator for user types
 */
const userTypeArbitrary = fc.constantFrom('teacher' as const, 'student' as const);

/**
 * Generator for valid user info
 */
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

/**
 * Generator for login parameters
 */
const loginParamsArbitrary = fc.record({
  account: fc.oneof(
    fc.emailAddress(),
    fc.string({ minLength: 5, maxLength: 20 })
  ),
  password: fc.string({ minLength: 6, maxLength: 50 }),
  user_type: userTypeArbitrary,
});

/**
 * Generator for complete login result
 */
const loginResultArbitrary = fc.record({
  access_token: accessTokenArbitrary,
  refresh_token: refreshTokenArbitrary,
  token_type: fc.constant('Bearer'),
  expires_in: expiresInArbitrary,
  user: userInfoArbitrary,
});

describe('Auth Service - Property-Based Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Mock window.location for logout tests
    delete (window as any).location;
    (window as any).location = { href: '' };
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('Property 4: Token Storage on Login', () => {
    /**
     * **Validates: Requirements 2.4**
     * 
     * Property: For any successful login response containing access_token and refresh_token,
     * the TokenManager should store both tokens to localStorage with correct key names.
     */
    it('should store access_token and refresh_token for any successful login response', () => {
      fc.assert(
        fc.property(loginParamsArbitrary, loginResultArbitrary, async (loginParams, loginResult) => {
          // Arrange: Mock API response
          vi.mocked(api.post).mockResolvedValue(loginResult);

          // Act: Perform login
          await AuthService.login(loginParams);

          // Assert: TokenManager.setTokens should be called with correct token data
          expect(TokenManager.setTokens).toHaveBeenCalledWith({
            access_token: loginResult.access_token,
            refresh_token: loginResult.refresh_token,
            token_type: loginResult.token_type,
            expires_in: loginResult.expires_in,
          });
          expect(TokenManager.setTokens).toHaveBeenCalledTimes(1);
        }),
        { numRuns: 100 }
      );
    });

    it('should store tokens with correct structure for any valid login result', () => {
      fc.assert(
        fc.property(loginParamsArbitrary, loginResultArbitrary, async (loginParams, loginResult) => {
          // Arrange: Mock API response
          vi.mocked(api.post).mockResolvedValue(loginResult);

          // Track what was passed to setTokens
          let capturedTokenData: TokenData | null = null;
          vi.mocked(TokenManager.setTokens).mockImplementation((tokenData: TokenData) => {
            capturedTokenData = tokenData;
          });

          // Act: Perform login
          await AuthService.login(loginParams);

          // Assert: Captured token data should have all required fields
          expect(capturedTokenData).not.toBeNull();
          expect(capturedTokenData).toHaveProperty('access_token');
          expect(capturedTokenData).toHaveProperty('refresh_token');
          expect(capturedTokenData).toHaveProperty('token_type');
          expect(capturedTokenData).toHaveProperty('expires_in');
          
          // Verify values match the login result
          expect(capturedTokenData?.access_token).toBe(loginResult.access_token);
          expect(capturedTokenData?.refresh_token).toBe(loginResult.refresh_token);
          expect(capturedTokenData?.token_type).toBe(loginResult.token_type);
          expect(capturedTokenData?.expires_in).toBe(loginResult.expires_in);
        }),
        { numRuns: 100 }
      );
    });

    it('should not store tokens when login fails', () => {
      fc.assert(
        fc.property(loginParamsArbitrary, async (loginParams) => {
          // Arrange: Mock API failure
          const error = new Error('Login failed');
          vi.mocked(api.post).mockRejectedValue(error);

          // Act & Assert: Login should throw and not store tokens
          await expect(AuthService.login(loginParams)).rejects.toThrow('Login failed');
          expect(TokenManager.setTokens).not.toHaveBeenCalled();
          expect(TokenManager.setUserInfo).not.toHaveBeenCalled();
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
     * Note: In this implementation, TokenManager acts as the state persistence layer.
     */
    it('should store user info for any successful login response', () => {
      fc.assert(
        fc.property(loginParamsArbitrary, loginResultArbitrary, async (loginParams, loginResult) => {
          // Arrange: Mock API response
          vi.mocked(api.post).mockResolvedValue(loginResult);

          // Act: Perform login
          await AuthService.login(loginParams);

          // Assert: TokenManager.setUserInfo should be called with user data
          expect(TokenManager.setUserInfo).toHaveBeenCalledWith(loginResult.user);
          expect(TokenManager.setUserInfo).toHaveBeenCalledTimes(1);
        }),
        { numRuns: 100 }
      );
    });

    it('should store complete user info with all fields for any valid login result', () => {
      fc.assert(
        fc.property(loginParamsArbitrary, loginResultArbitrary, async (loginParams, loginResult) => {
          // Arrange: Mock API response
          vi.mocked(api.post).mockResolvedValue(loginResult);

          // Track what was passed to setUserInfo
          let capturedUserInfo: UserInfo | null = null;
          vi.mocked(TokenManager.setUserInfo).mockImplementation((userInfo: UserInfo) => {
            capturedUserInfo = userInfo;
          });

          // Act: Perform login
          await AuthService.login(loginParams);

          // Assert: Captured user info should match login result user
          expect(capturedUserInfo).not.toBeNull();
          expect(capturedUserInfo).toEqual(loginResult.user);
          
          // Verify required fields
          expect(capturedUserInfo?.id).toBe(loginResult.user.id);
          expect(capturedUserInfo?.name).toBe(loginResult.user.name);
          expect(capturedUserInfo?.email).toBe(loginResult.user.email);
          expect(capturedUserInfo?.user_type).toBe(loginResult.user.user_type);
        }),
        { numRuns: 100 }
      );
    });

    it('should store tokens before storing user info for any login', () => {
      fc.assert(
        fc.property(loginParamsArbitrary, loginResultArbitrary, async (loginParams, loginResult) => {
          // Arrange: Mock API response
          vi.mocked(api.post).mockResolvedValue(loginResult);

          // Track call order
          const callOrder: string[] = [];
          vi.mocked(TokenManager.setTokens).mockImplementation(() => {
            callOrder.push('setTokens');
          });
          vi.mocked(TokenManager.setUserInfo).mockImplementation(() => {
            callOrder.push('setUserInfo');
          });

          // Act: Perform login
          await AuthService.login(loginParams);

          // Assert: setTokens should be called before setUserInfo
          expect(callOrder).toEqual(['setTokens', 'setUserInfo']);
        }),
        { numRuns: 100 }
      );
    });

    it('should preserve all optional user fields during state update', () => {
      fc.assert(
        fc.property(
          loginParamsArbitrary,
          fc.record({
            access_token: accessTokenArbitrary,
            refresh_token: refreshTokenArbitrary,
            token_type: fc.constant('Bearer'),
            expires_in: expiresInArbitrary,
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
            // Arrange: Mock API response with all optional fields
            vi.mocked(api.post).mockResolvedValue(loginResult);

            // Track what was passed to setUserInfo
            let capturedUserInfo: UserInfo | null = null;
            vi.mocked(TokenManager.setUserInfo).mockImplementation((userInfo: UserInfo) => {
              capturedUserInfo = userInfo;
            });

            // Act: Perform login
            await AuthService.login(loginParams);

            // Assert: All optional fields should be preserved
            expect(capturedUserInfo?.avatar).toBe(loginResult.user.avatar);
            expect(capturedUserInfo?.phone).toBe(loginResult.user.phone);
            expect(capturedUserInfo?.student_id).toBe(loginResult.user.student_id);
            expect(capturedUserInfo?.created_at).toBe(loginResult.user.created_at);
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should handle user info with missing optional fields', () => {
      fc.assert(
        fc.property(
          loginParamsArbitrary,
          fc.record({
            access_token: accessTokenArbitrary,
            refresh_token: refreshTokenArbitrary,
            token_type: fc.constant('Bearer'),
            expires_in: expiresInArbitrary,
            user: fc.record({
              id: fc.uuid(),
              name: fc.string({ minLength: 1, maxLength: 50 }),
              email: fc.emailAddress(),
              user_type: userTypeArbitrary,
              // No optional fields
            }),
          }),
          async (loginParams, loginResult) => {
            // Arrange: Mock API response with minimal user info
            vi.mocked(api.post).mockResolvedValue(loginResult);

            // Track what was passed to setUserInfo
            let capturedUserInfo: UserInfo | null = null;
            vi.mocked(TokenManager.setUserInfo).mockImplementation((userInfo: UserInfo) => {
              capturedUserInfo = userInfo;
            });

            // Act: Perform login
            await AuthService.login(loginParams);

            // Assert: Should store user info even without optional fields
            expect(capturedUserInfo).not.toBeNull();
            expect(capturedUserInfo?.id).toBe(loginResult.user.id);
            expect(capturedUserInfo?.name).toBe(loginResult.user.name);
            expect(capturedUserInfo?.email).toBe(loginResult.user.email);
            expect(capturedUserInfo?.user_type).toBe(loginResult.user.user_type);
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
          // Act: Perform logout
          AuthService.logout();

          // Assert: TokenManager.clearAll should be called
          expect(TokenManager.clearAll).toHaveBeenCalledTimes(1);
        }),
        { numRuns: 100 }
      );
    });

    it('should clear authentication data regardless of current state', () => {
      fc.assert(
        fc.property(
          fc.option(loginResultArbitrary, { nil: null }),
          (loginResult) => {
            // Arrange: Optionally set up logged-in state
            if (loginResult) {
              vi.mocked(api.post).mockResolvedValue(loginResult);
              // Simulate being logged in
              vi.mocked(TokenManager.getAccessToken).mockReturnValue(loginResult.access_token);
              vi.mocked(TokenManager.getUserInfo).mockReturnValue(loginResult.user);
            } else {
              // Simulate not being logged in
              vi.mocked(TokenManager.getAccessToken).mockReturnValue(null);
              vi.mocked(TokenManager.getUserInfo).mockReturnValue(null);
            }

            // Act: Perform logout
            AuthService.logout();

            // Assert: clearAll should be called regardless of state
            expect(TokenManager.clearAll).toHaveBeenCalledTimes(1);
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should redirect to login page after clearing authentication data', () => {
      fc.assert(
        fc.property(fc.constant(null), () => {
          // Arrange: Reset window.location
          (window as any).location = { href: '' };

          // Act: Perform logout
          AuthService.logout();

          // Assert: Should redirect to login page
          expect(window.location.href).toBe('/login');
        }),
        { numRuns: 100 }
      );
    });

    it('should clear authentication data even if redirect fails', () => {
      fc.assert(
        fc.property(fc.constant(null), () => {
          // Arrange: Make redirect throw an error
          const originalLocation = window.location;
          delete (window as any).location;
          (window as any).location = {
            get href() {
              throw new Error('Redirect failed');
            },
            set href(value: string) {
              throw new Error('Redirect failed');
            },
          };

          // Act: Perform logout (should not throw)
          AuthService.logout();

          // Assert: clearAll should still be called
          expect(TokenManager.clearAll).toHaveBeenCalledTimes(1);

          // Cleanup
          (window as any).location = originalLocation;
        }),
        { numRuns: 100 }
      );
    });

    it('should be idempotent - multiple logouts should work correctly', () => {
      fc.assert(
        fc.property(fc.integer({ min: 1, max: 5 }), (logoutCount) => {
          // Act: Perform logout multiple times
          for (let i = 0; i < logoutCount; i++) {
            AuthService.logout();
          }

          // Assert: clearAll should be called for each logout
          expect(TokenManager.clearAll).toHaveBeenCalledTimes(logoutCount);
        }),
        { numRuns: 100 }
      );
    });

    it('should handle logout errors gracefully without throwing', () => {
      fc.assert(
        fc.property(fc.constant(null), () => {
          // Arrange: Make clearAll throw an error
          vi.mocked(TokenManager.clearAll).mockImplementation(() => {
            throw new Error('Clear failed');
          });

          // Act & Assert: Logout should not throw
          expect(() => AuthService.logout()).not.toThrow();
        }),
        { numRuns: 100 }
      );
    });
  });

  describe('Integration Properties', () => {
    /**
     * Test the complete login-logout cycle
     */
    it('should maintain data integrity through login-logout cycle', () => {
      fc.assert(
        fc.property(loginParamsArbitrary, loginResultArbitrary, async (loginParams, loginResult) => {
          // Arrange: Mock API response
          vi.mocked(api.post).mockResolvedValue(loginResult);

          // Act: Login
          await AuthService.login(loginParams);

          // Assert: Data should be stored
          expect(TokenManager.setTokens).toHaveBeenCalledWith({
            access_token: loginResult.access_token,
            refresh_token: loginResult.refresh_token,
            token_type: loginResult.token_type,
            expires_in: loginResult.expires_in,
          });
          expect(TokenManager.setUserInfo).toHaveBeenCalledWith(loginResult.user);

          // Act: Logout
          AuthService.logout();

          // Assert: Data should be cleared
          expect(TokenManager.clearAll).toHaveBeenCalled();
        }),
        { numRuns: 100 }
      );
    });

    it('should handle multiple login attempts with different credentials', () => {
      fc.assert(
        fc.property(
          fc.array(
            fc.tuple(loginParamsArbitrary, loginResultArbitrary),
            { minLength: 2, maxLength: 5 }
          ),
          async (loginAttempts) => {
            // Act: Perform multiple logins
            for (const [loginParams, loginResult] of loginAttempts) {
              vi.mocked(api.post).mockResolvedValue(loginResult);
              await AuthService.login(loginParams);
            }

            // Assert: setTokens and setUserInfo should be called for each login
            expect(TokenManager.setTokens).toHaveBeenCalledTimes(loginAttempts.length);
            expect(TokenManager.setUserInfo).toHaveBeenCalledTimes(loginAttempts.length);

            // The last call should have the last login result
            const lastLoginResult = loginAttempts[loginAttempts.length - 1][1];
            expect(TokenManager.setUserInfo).toHaveBeenLastCalledWith(lastLoginResult.user);
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should maintain correct state after failed login followed by successful login', () => {
      fc.assert(
        fc.property(
          loginParamsArbitrary,
          loginParamsArbitrary,
          loginResultArbitrary,
          async (failedParams, successParams, successResult) => {
            // Arrange: First login fails
            vi.mocked(api.post).mockRejectedValueOnce(new Error('Login failed'));

            // Act: Failed login
            await expect(AuthService.login(failedParams)).rejects.toThrow();

            // Assert: No data should be stored after failed login
            expect(TokenManager.setTokens).not.toHaveBeenCalled();
            expect(TokenManager.setUserInfo).not.toHaveBeenCalled();

            // Arrange: Second login succeeds
            vi.mocked(api.post).mockResolvedValueOnce(successResult);

            // Act: Successful login
            await AuthService.login(successParams);

            // Assert: Data should be stored after successful login
            expect(TokenManager.setTokens).toHaveBeenCalledTimes(1);
            expect(TokenManager.setUserInfo).toHaveBeenCalledTimes(1);
            expect(TokenManager.setUserInfo).toHaveBeenCalledWith(successResult.user);
          }
        ),
        { numRuns: 100 }
      );
    });
  });

  describe('Edge Cases and Robustness', () => {
    it('should handle login with minimal token expiration time', () => {
      fc.assert(
        fc.property(
          loginParamsArbitrary,
          fc.record({
            access_token: accessTokenArbitrary,
            refresh_token: refreshTokenArbitrary,
            token_type: fc.constant('Bearer'),
            expires_in: fc.constant(1), // 1 second
            user: userInfoArbitrary,
          }),
          async (loginParams, loginResult) => {
            // Arrange: Mock API response with minimal expiration
            vi.mocked(api.post).mockResolvedValue(loginResult);

            // Act: Perform login
            await AuthService.login(loginParams);

            // Assert: Should still store tokens correctly
            expect(TokenManager.setTokens).toHaveBeenCalledWith({
              access_token: loginResult.access_token,
              refresh_token: loginResult.refresh_token,
              token_type: loginResult.token_type,
              expires_in: 1,
            });
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should handle login with very long token expiration time', () => {
      fc.assert(
        fc.property(
          loginParamsArbitrary,
          fc.record({
            access_token: accessTokenArbitrary,
            refresh_token: refreshTokenArbitrary,
            token_type: fc.constant('Bearer'),
            expires_in: fc.constant(31536000), // 1 year in seconds
            user: userInfoArbitrary,
          }),
          async (loginParams, loginResult) => {
            // Arrange: Mock API response with long expiration
            vi.mocked(api.post).mockResolvedValue(loginResult);

            // Act: Perform login
            await AuthService.login(loginParams);

            // Assert: Should still store tokens correctly
            expect(TokenManager.setTokens).toHaveBeenCalledWith({
              access_token: loginResult.access_token,
              refresh_token: loginResult.refresh_token,
              token_type: loginResult.token_type,
              expires_in: 31536000,
            });
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should handle user info with special characters in name', () => {
      fc.assert(
        fc.property(
          loginParamsArbitrary,
          fc.record({
            access_token: accessTokenArbitrary,
            refresh_token: refreshTokenArbitrary,
            token_type: fc.constant('Bearer'),
            expires_in: expiresInArbitrary,
            user: fc.record({
              id: fc.uuid(),
              name: fc.string({ minLength: 1, maxLength: 50 }), // Can include special chars
              email: fc.emailAddress(),
              user_type: userTypeArbitrary,
            }),
          }),
          async (loginParams, loginResult) => {
            // Arrange: Mock API response
            vi.mocked(api.post).mockResolvedValue(loginResult);

            // Act: Perform login
            await AuthService.login(loginParams);

            // Assert: Should store user info with special characters correctly
            expect(TokenManager.setUserInfo).toHaveBeenCalledWith(loginResult.user);
          }
        ),
        { numRuns: 100 }
      );
    });
  });
});
