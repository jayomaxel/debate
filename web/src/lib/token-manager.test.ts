import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import * as fc from 'fast-check';
import TokenManager from './token-manager';

const fixedNow = 1_700_000_000_000;
const isoDateArbitrary = fc
  .integer({
    min: Date.parse('2000-01-01T00:00:00.000Z'),
    max: Date.parse('2100-12-31T23:59:59.999Z'),
  })
  .map((timestamp) => new Date(timestamp).toISOString());
const userTypeArbitrary = fc.constantFrom('teacher' as const, 'student' as const, 'administrator' as const);

const tokenDataArbitrary = fc.record({
  access_token: fc.string({ minLength: 20, maxLength: 200 }),
  refresh_token: fc.string({ minLength: 20, maxLength: 200 }),
  token_type: fc.constant('Bearer'),
  expires_in: fc.integer({ min: 300, max: 86_400 }),
});

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

describe('Token Manager - Property-Based Tests', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
    vi.spyOn(Date, 'now').mockReturnValue(fixedNow);
  });

  afterEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it('stores and retrieves tokens with the current storage contract', () => {
    fc.assert(
      fc.property(tokenDataArbitrary, (tokenData) => {
        TokenManager.setTokens(tokenData);

        expect(localStorage.getItem('access_token')).toBe(tokenData.access_token);
        expect(localStorage.getItem('refresh_token')).toBe(tokenData.refresh_token);
        expect(localStorage.getItem('token_expires_at')).toBe(
          String(fixedNow + tokenData.expires_in * 1000)
        );

        expect(TokenManager.getAccessToken()).toBe(tokenData.access_token);
        expect(TokenManager.getRefreshToken()).toBe(tokenData.refresh_token);

        localStorage.clear();
      }),
      { numRuns: 100 }
    );
  });

  it('persists user info using the current UserInfo shape', () => {
    fc.assert(
      fc.property(userInfoArbitrary, (userInfo) => {
        TokenManager.setUserInfo(userInfo);

        expect(localStorage.getItem('user_info')).toBe(JSON.stringify(userInfo));
        expect(TokenManager.getUserInfo()).toEqual(userInfo);

        localStorage.clear();
      }),
      { numRuns: 100 }
    );
  });

  it('clearAll removes tokens and user info together', () => {
    fc.assert(
      fc.property(tokenDataArbitrary, userInfoArbitrary, (tokenData, userInfo) => {
        TokenManager.setTokens(tokenData);
        TokenManager.setUserInfo(userInfo);

        TokenManager.clearAll();

        expect(localStorage.getItem('access_token')).toBeNull();
        expect(localStorage.getItem('refresh_token')).toBeNull();
        expect(localStorage.getItem('token_expires_at')).toBeNull();
        expect(localStorage.getItem('user_info')).toBeNull();
      }),
      { numRuns: 100 }
    );
  });

  it('clearing only tokens keeps persisted user info intact', () => {
    fc.assert(
      fc.property(tokenDataArbitrary, userInfoArbitrary, (tokenData, userInfo) => {
        TokenManager.setTokens(tokenData);
        TokenManager.setUserInfo(userInfo);

        TokenManager.clearTokens();

        expect(TokenManager.getAccessToken()).toBeNull();
        expect(TokenManager.getRefreshToken()).toBeNull();
        expect(TokenManager.getUserInfo()).toEqual(userInfo);

        localStorage.clear();
      }),
      { numRuns: 100 }
    );
  });

  it('multiple user updates keep the latest persisted value', () => {
    fc.assert(
      fc.property(fc.array(userInfoArbitrary, { minLength: 2, maxLength: 5 }), (userInfos) => {
        for (const userInfo of userInfos) {
          TokenManager.setUserInfo(userInfo);
        }

        expect(TokenManager.getUserInfo()).toEqual(userInfos[userInfos.length - 1]);

        localStorage.clear();
      }),
      { numRuns: 100 }
    );
  });

  it('returns null when authentication data does not exist', () => {
    fc.assert(
      fc.property(fc.constant(null), () => {
        localStorage.clear();

        expect(TokenManager.getAccessToken()).toBeNull();
        expect(TokenManager.getRefreshToken()).toBeNull();
        expect(TokenManager.getUserInfo()).toBeNull();
      }),
      { numRuns: 100 }
    );
  });
});
