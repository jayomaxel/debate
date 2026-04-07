import { beforeEach, describe, expect, it, vi } from 'vitest';
import * as fc from 'fast-check';
import AuthService from './auth.service';
import TokenManager, { type TokenData, type UserInfo } from '../lib/token-manager';
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
  },
}));

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

const loginParamsArbitrary = fc.record({
  account: fc.oneof(fc.emailAddress(), fc.string({ minLength: 5, maxLength: 20 })),
  password: fc.string({ minLength: 6, maxLength: 50 }),
  user_type: userTypeArbitrary,
});

const loginResultArbitrary = fc.tuple(tokenDataArbitrary, userInfoArbitrary).map(
  ([tokenData, user]): TokenData & { user: UserInfo } => ({
    ...tokenData,
    user,
  })
);

function mockLocation() {
  delete (window as any).location;
  (window as any).location = { href: '' };
}

describe('Auth Service - Property-Based Tests', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mockLocation();
  });

  it('stores token data and user info for successful logins', async () => {
    await fc.assert(
      fc.asyncProperty(loginParamsArbitrary, loginResultArbitrary, async (loginParams, loginResult) => {
        vi.mocked(api.post).mockResolvedValue(loginResult);

        const result = await AuthService.login(loginParams);

        expect(result).toEqual(loginResult);
        expect(api.post).toHaveBeenCalledWith('/api/auth/login', loginParams);
        expect(TokenManager.setTokens).toHaveBeenCalledWith({
          access_token: loginResult.access_token,
          refresh_token: loginResult.refresh_token,
          token_type: loginResult.token_type,
          expires_in: loginResult.expires_in,
        });
        expect(TokenManager.setUserInfo).toHaveBeenCalledWith(loginResult.user);

        vi.clearAllMocks();
      }),
      { numRuns: 100 }
    );
  });

  it('stores tokens before persisting user info', async () => {
    await fc.assert(
      fc.asyncProperty(loginParamsArbitrary, loginResultArbitrary, async (loginParams, loginResult) => {
        vi.mocked(api.post).mockResolvedValue(loginResult);
        const callOrder: string[] = [];

        vi.mocked(TokenManager.setTokens).mockImplementation(() => {
          callOrder.push('setTokens');
        });
        vi.mocked(TokenManager.setUserInfo).mockImplementation(() => {
          callOrder.push('setUserInfo');
        });

        await AuthService.login(loginParams);

        expect(callOrder).toEqual(['setTokens', 'setUserInfo']);

        vi.clearAllMocks();
      }),
      { numRuns: 100 }
    );
  });

  it('does not persist anything when login fails', async () => {
    await fc.assert(
      fc.asyncProperty(loginParamsArbitrary, fc.string({ minLength: 1, maxLength: 100 }), async (loginParams, message) => {
        const error = new Error(message);
        vi.mocked(api.post).mockRejectedValue(error);

        await expect(AuthService.login(loginParams)).rejects.toBe(error);
        expect(TokenManager.setTokens).not.toHaveBeenCalled();
        expect(TokenManager.setUserInfo).not.toHaveBeenCalled();

        vi.clearAllMocks();
      }),
      { numRuns: 100 }
    );
  });

  it('clears auth state and redirects on logout', () => {
    fc.assert(
      fc.property(fc.constant(null), () => {
        mockLocation();

        AuthService.logout();

        expect(TokenManager.clearAll).toHaveBeenCalledTimes(1);
        expect(window.location.href).toBe('/login');

        vi.clearAllMocks();
      }),
      { numRuns: 100 }
    );
  });

  it('swallows clearAll errors during logout and leaves location unchanged', () => {
    fc.assert(
      fc.property(fc.string({ minLength: 1, maxLength: 100 }), (message) => {
        mockLocation();
        vi.mocked(TokenManager.clearAll).mockImplementation(() => {
          throw new Error(message);
        });

        expect(() => AuthService.logout()).not.toThrow();
        expect(TokenManager.clearAll).toHaveBeenCalledTimes(1);
        expect(window.location.href).toBe('');

        vi.clearAllMocks();
      }),
      { numRuns: 100 }
    );
  });

  it('supports a full login then logout cycle', async () => {
    await fc.assert(
      fc.asyncProperty(loginParamsArbitrary, loginResultArbitrary, async (loginParams, loginResult) => {
        vi.mocked(api.post).mockResolvedValue(loginResult);
        mockLocation();

        await AuthService.login(loginParams);
        AuthService.logout();

        expect(TokenManager.setTokens).toHaveBeenCalledTimes(1);
        expect(TokenManager.setUserInfo).toHaveBeenCalledTimes(1);
        expect(TokenManager.clearAll).toHaveBeenCalledTimes(1);
        expect(window.location.href).toBe('/login');

        vi.clearAllMocks();
      }),
      { numRuns: 100 }
    );
  });
});
