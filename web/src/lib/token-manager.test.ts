/**
 * Property-Based Tests for Token Manager
 * 
 * Feature: frontend-backend-integration
 * Tests Properties 4, 6, and 19 from the design document
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import * as fc from 'fast-check';
import TokenManager, { TokenData, UserInfo } from './token-manager';

// Arbitraries (generators) for property-based testing
const tokenDataArbitrary = fc.record({
  access_token: fc.string({ minLength: 20, maxLength: 200 }),
  refresh_token: fc.string({ minLength: 20, maxLength: 200 }),
  token_type: fc.constant('Bearer'),
  expires_in: fc.integer({ min: 300, max: 86400 }), // 5 minutes to 24 hours
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

describe('Token Manager - Property-Based Tests', () => {
  beforeEach(() => {
    // Clear localStorage before each test
    localStorage.clear();
    vi.clearAllMocks();
  });

  describe('Property 4: Token Storage on Login', () => {
    /**
     * **Validates: Requirements 2.4**
     * 
     * Property: For any successful login response containing access_token and refresh_token,
     * the TokenManager should store both tokens to localStorage with correct key names.
     */
    it('should store access_token and refresh_token to localStorage with correct keys for any valid TokenData', () => {
      fc.assert(
        fc.property(tokenDataArbitrary, (tokenData) => {
          // Act: Store tokens
          TokenManager.setTokens(tokenData);

          // Assert: Tokens should be stored with correct keys
          const storedAccessToken = localStorage.getItem('access_token');
          const storedRefreshToken = localStorage.getItem('refresh_token');
          const storedExpiresAt = localStorage.getItem('token_expires_at');

          expect(storedAccessToken).toBe(tokenData.access_token);
          expect(storedRefreshToken).toBe(tokenData.refresh_token);
          expect(storedExpiresAt).toBeDefined();
          
          // Verify expires_at is calculated correctly (within 1 second tolerance)
          const expectedExpiresAt = Date.now() + tokenData.expires_in * 1000;
          const actualExpiresAt = parseInt(storedExpiresAt!, 10);
          expect(Math.abs(actualExpiresAt - expectedExpiresAt)).toBeLessThan(1000);

          // Cleanup for next iteration
          localStorage.clear();
        }),
        { numRuns: 100 }
      );
    });

    it('should retrieve stored tokens correctly for any valid TokenData', () => {
      fc.assert(
        fc.property(tokenDataArbitrary, (tokenData) => {
          // Arrange & Act: Store and retrieve tokens
          TokenManager.setTokens(tokenData);
          const retrievedAccessToken = TokenManager.getAccessToken();
          const retrievedRefreshToken = TokenManager.getRefreshToken();

          // Assert: Retrieved tokens should match stored tokens
          expect(retrievedAccessToken).toBe(tokenData.access_token);
          expect(retrievedRefreshToken).toBe(tokenData.refresh_token);

          // Cleanup
          localStorage.clear();
        }),
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
    it('should remove all authentication-related items from localStorage on logout', () => {
      fc.assert(
        fc.property(tokenDataArbitrary, userInfoArbitrary, (tokenData, userInfo) => {
          // Arrange: Store tokens and user info
          TokenManager.setTokens(tokenData);
          TokenManager.setUserInfo(userInfo);

          // Verify data is stored
          expect(localStorage.getItem('access_token')).toBeDefined();
          expect(localStorage.getItem('refresh_token')).toBeDefined();
          expect(localStorage.getItem('token_expires_at')).toBeDefined();
          expect(localStorage.getItem('user_info')).toBeDefined();

          // Act: Clear tokens and user info (logout)
          TokenManager.clearTokens();
          TokenManager.clearUserInfo();

          // Assert: All authentication data should be removed
          expect(localStorage.getItem('access_token')).toBeNull();
          expect(localStorage.getItem('refresh_token')).toBeNull();
          expect(localStorage.getItem('token_expires_at')).toBeNull();
          expect(localStorage.getItem('user_info')).toBeNull();

          // Cleanup
          localStorage.clear();
        }),
        { numRuns: 100 }
      );
    });

    it('should use clearAll() to remove all authentication data in one call', () => {
      fc.assert(
        fc.property(tokenDataArbitrary, userInfoArbitrary, (tokenData, userInfo) => {
          // Arrange: Store tokens and user info
          TokenManager.setTokens(tokenData);
          TokenManager.setUserInfo(userInfo);

          // Act: Clear all authentication data
          TokenManager.clearAll();

          // Assert: All authentication data should be removed
          expect(localStorage.getItem('access_token')).toBeNull();
          expect(localStorage.getItem('refresh_token')).toBeNull();
          expect(localStorage.getItem('token_expires_at')).toBeNull();
          expect(localStorage.getItem('user_info')).toBeNull();

          // Cleanup
          localStorage.clear();
        }),
        { numRuns: 100 }
      );
    });

    it('should handle clearing tokens when no tokens exist (idempotent)', () => {
      fc.assert(
        fc.property(fc.constant(null), () => {
          // Arrange: Ensure localStorage is empty
          localStorage.clear();

          // Act: Clear tokens when none exist
          TokenManager.clearTokens();
          TokenManager.clearUserInfo();

          // Assert: Should not throw and localStorage should remain empty
          expect(localStorage.getItem('access_token')).toBeNull();
          expect(localStorage.getItem('refresh_token')).toBeNull();
          expect(localStorage.getItem('token_expires_at')).toBeNull();
          expect(localStorage.getItem('user_info')).toBeNull();
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
     * 
     * Note: This tests the TokenManager's role in state persistence (storing user info).
     */
    it('should persist user info to localStorage for any valid UserInfo', () => {
      fc.assert(
        fc.property(userInfoArbitrary, (userInfo) => {
          // Act: Store user info
          TokenManager.setUserInfo(userInfo);

          // Assert: User info should be persisted to localStorage
          const storedUserInfoStr = localStorage.getItem('user_info');
          expect(storedUserInfoStr).toBeDefined();
          
          const storedUserInfo = JSON.parse(storedUserInfoStr!);
          expect(storedUserInfo).toEqual(userInfo);

          // Cleanup
          localStorage.clear();
        }),
        { numRuns: 100 }
      );
    });

    it('should retrieve persisted user info correctly for any valid UserInfo', () => {
      fc.assert(
        fc.property(userInfoArbitrary, (userInfo) => {
          // Arrange & Act: Store and retrieve user info
          TokenManager.setUserInfo(userInfo);
          const retrievedUserInfo = TokenManager.getUserInfo();

          // Assert: Retrieved user info should match stored user info
          expect(retrievedUserInfo).toEqual(userInfo);

          // Cleanup
          localStorage.clear();
        }),
        { numRuns: 100 }
      );
    });

    it('should maintain state persistence across multiple updates', () => {
      fc.assert(
        fc.property(fc.array(userInfoArbitrary, { minLength: 2, maxLength: 5 }), (userInfos) => {
          // Act: Update user info multiple times
          for (const userInfo of userInfos) {
            TokenManager.setUserInfo(userInfo);
            
            // Assert: Each update should be persisted correctly
            const retrievedUserInfo = TokenManager.getUserInfo();
            expect(retrievedUserInfo).toEqual(userInfo);
          }

          // Assert: Final state should be the last update
          const finalUserInfo = TokenManager.getUserInfo();
          expect(finalUserInfo).toEqual(userInfos[userInfos.length - 1]);

          // Cleanup
          localStorage.clear();
        }),
        { numRuns: 100 }
      );
    });

    it('should persist both tokens and user info independently', () => {
      fc.assert(
        fc.property(tokenDataArbitrary, userInfoArbitrary, (tokenData, userInfo) => {
          // Act: Store tokens and user info
          TokenManager.setTokens(tokenData);
          TokenManager.setUserInfo(userInfo);

          // Assert: Both should be persisted independently
          const retrievedAccessToken = TokenManager.getAccessToken();
          const retrievedRefreshToken = TokenManager.getRefreshToken();
          const retrievedUserInfo = TokenManager.getUserInfo();

          expect(retrievedAccessToken).toBe(tokenData.access_token);
          expect(retrievedRefreshToken).toBe(tokenData.refresh_token);
          expect(retrievedUserInfo).toEqual(userInfo);

          // Act: Clear only tokens
          TokenManager.clearTokens();

          // Assert: User info should still be persisted
          expect(TokenManager.getAccessToken()).toBeNull();
          expect(TokenManager.getRefreshToken()).toBeNull();
          expect(TokenManager.getUserInfo()).toEqual(userInfo);

          // Cleanup
          localStorage.clear();
        }),
        { numRuns: 100 }
      );
    });
  });

  describe('Edge Cases and Robustness', () => {
    it('should handle empty strings in token data', () => {
      fc.assert(
        fc.property(
          fc.record({
            access_token: fc.constant(''),
            refresh_token: fc.constant(''),
            token_type: fc.constant('Bearer'),
            expires_in: fc.integer({ min: 300, max: 86400 }),
          }),
          (tokenData) => {
            // Act: Store tokens with empty strings
            TokenManager.setTokens(tokenData);

            // Assert: Empty strings should be stored and retrieved
            // localStorage stores empty strings as empty strings, not null
            const accessToken = TokenManager.getAccessToken();
            const refreshToken = TokenManager.getRefreshToken();
            
            // Empty strings are stored, so they should be retrievable as empty strings
            expect(accessToken).toBe('');
            expect(refreshToken).toBe('');
            
            // Verify they are actually stored in localStorage
            expect(localStorage.getItem('access_token')).toBe('');
            expect(localStorage.getItem('refresh_token')).toBe('');

            // Cleanup
            localStorage.clear();
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should return null when retrieving non-existent tokens', () => {
      fc.assert(
        fc.property(fc.constant(null), () => {
          // Arrange: Ensure localStorage is empty
          localStorage.clear();

          // Act & Assert: Should return null for non-existent tokens
          expect(TokenManager.getAccessToken()).toBeNull();
          expect(TokenManager.getRefreshToken()).toBeNull();
          expect(TokenManager.getUserInfo()).toBeNull();
        }),
        { numRuns: 100 }
      );
    });

    it('should handle special characters in user info', () => {
      fc.assert(
        fc.property(
          fc.record({
            id: fc.uuid(),
            name: fc.string({ minLength: 1, maxLength: 50 }),
            email: fc.emailAddress(),
            user_type: fc.constantFrom('teacher' as const, 'student' as const),
            avatar: fc.option(fc.string(), { nil: undefined }),
            phone: fc.option(fc.string(), { nil: undefined }),
            student_id: fc.option(fc.string(), { nil: undefined }),
            created_at: fc.option(fc.string(), { nil: undefined }),
          }),
          (userInfo) => {
            // Act: Store and retrieve user info with special characters
            TokenManager.setUserInfo(userInfo);
            const retrieved = TokenManager.getUserInfo();

            // Assert: Should handle special characters correctly
            expect(retrieved).toEqual(userInfo);

            // Cleanup
            localStorage.clear();
          }
        ),
        { numRuns: 100 }
      );
    });
  });
});
