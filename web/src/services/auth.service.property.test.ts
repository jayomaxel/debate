import { beforeEach, describe, expect, it, vi } from 'vitest';
import * as fc from 'fast-check';
import AuthService from './auth.service';
import TokenManager, { type UserInfo } from '../lib/token-manager';
import { api } from '../lib/api';

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

const isoDateArbitrary = fc
  .integer({
    min: Date.parse('2000-01-01T00:00:00.000Z'),
    max: Date.parse('2100-12-31T23:59:59.999Z'),
  })
  .map((timestamp) => new Date(timestamp).toISOString());
const userTypeArbitrary = fc.constantFrom('teacher' as const, 'student' as const, 'administrator' as const);

const loginParamsArbitrary = fc.record({
  account: fc.oneof(fc.emailAddress(), fc.string({ minLength: 5, maxLength: 20 })),
  password: fc.string({ minLength: 6, maxLength: 50 }),
  user_type: userTypeArbitrary,
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

const loginResultArbitrary = fc.record({
  access_token: fc.string({ minLength: 20, maxLength: 200 }),
  refresh_token: fc.string({ minLength: 20, maxLength: 200 }),
  token_type: fc.constant('Bearer'),
  expires_in: fc.integer({ min: 300, max: 86_400 }),
  user: userInfoArbitrary,
});

function mockLocation() {
  delete (window as any).location;
  (window as any).location = { href: '' };
}

describe('Auth Service - Contract Property Tests', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mockLocation();
  });

  it('passes login params through to the API and returns the API payload', async () => {
    await fc.assert(
      fc.asyncProperty(loginParamsArbitrary, loginResultArbitrary, async (loginParams, loginResult) => {
        vi.mocked(api.post).mockResolvedValue(loginResult);

        const result = await AuthService.login(loginParams);

        expect(api.post).toHaveBeenCalledWith('/api/auth/login', loginParams);
        expect(result).toEqual(loginResult);

        vi.clearAllMocks();
      }),
      { numRuns: 100 }
    );
  });

  it('persists the exact token and user payload produced by the current implementation', async () => {
    await fc.assert(
      fc.asyncProperty(loginParamsArbitrary, loginResultArbitrary, async (loginParams, loginResult) => {
        vi.mocked(api.post).mockResolvedValue(loginResult);
        let storedUserInfo: UserInfo | null = null;

        vi.mocked(TokenManager.setUserInfo).mockImplementation((userInfo: UserInfo) => {
          storedUserInfo = userInfo;
        });

        await AuthService.login(loginParams);

        expect(TokenManager.setTokens).toHaveBeenCalledWith({
          access_token: loginResult.access_token,
          refresh_token: loginResult.refresh_token,
          token_type: loginResult.token_type,
          expires_in: loginResult.expires_in,
        });
        expect(storedUserInfo).toEqual(loginResult.user);

        vi.clearAllMocks();
      }),
      { numRuns: 100 }
    );
  });

  it('preserves optional user fields without reshaping them', async () => {
    await fc.assert(
      fc.asyncProperty(
        loginParamsArbitrary,
        fc.record({
          access_token: fc.string({ minLength: 20, maxLength: 200 }),
          refresh_token: fc.string({ minLength: 20, maxLength: 200 }),
          token_type: fc.constant('Bearer'),
          expires_in: fc.integer({ min: 300, max: 86_400 }),
          user: fc.record({
            id: fc.uuid(),
            account: fc.oneof(fc.emailAddress(), fc.string({ minLength: 5, maxLength: 20 })),
            name: fc.string({ minLength: 1, maxLength: 50 }),
            email: fc.emailAddress(),
            user_type: userTypeArbitrary,
            avatar: fc.webUrl(),
            phone: fc.string({ minLength: 10, maxLength: 15 }),
            student_id: fc.string({ minLength: 5, maxLength: 20 }),
            class_id: fc.string({ minLength: 4, maxLength: 20 }),
            created_at: isoDateArbitrary,
          }),
        }),
        async (loginParams, loginResult) => {
          vi.mocked(api.post).mockResolvedValue(loginResult);

          await AuthService.login(loginParams);

          expect(TokenManager.setUserInfo).toHaveBeenCalledWith(loginResult.user);

          vi.clearAllMocks();
        }
      ),
      { numRuns: 100 }
    );
  });

  it('is idempotent across repeated logout calls', () => {
    fc.assert(
      fc.property(fc.integer({ min: 1, max: 5 }), (logoutCount) => {
        mockLocation();

        for (let index = 0; index < logoutCount; index++) {
          AuthService.logout();
        }

        expect(TokenManager.clearAll).toHaveBeenCalledTimes(logoutCount);
        expect(window.location.href).toBe('/login');

        vi.clearAllMocks();
      }),
      { numRuns: 100 }
    );
  });

  it('recovers cleanly from a failed login followed by a successful login', async () => {
    await fc.assert(
      fc.asyncProperty(
        loginParamsArbitrary,
        loginParamsArbitrary,
        loginResultArbitrary,
        async (failedParams, successParams, successResult) => {
          vi.mocked(api.post)
            .mockRejectedValueOnce(new Error('Login failed'))
            .mockResolvedValueOnce(successResult);

          await expect(AuthService.login(failedParams)).rejects.toThrow('Login failed');
          expect(TokenManager.setTokens).not.toHaveBeenCalled();
          expect(TokenManager.setUserInfo).not.toHaveBeenCalled();

          await AuthService.login(successParams);

          expect(TokenManager.setTokens).toHaveBeenCalledTimes(1);
          expect(TokenManager.setUserInfo).toHaveBeenCalledTimes(1);
          expect(TokenManager.setUserInfo).toHaveBeenCalledWith(successResult.user);

          vi.clearAllMocks();
        }
      ),
      { numRuns: 100 }
    );
  });
});
