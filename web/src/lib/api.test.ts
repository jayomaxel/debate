import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import * as fc from 'fast-check';
import axios, { AxiosHeaders } from 'axios';
import type { AxiosError, InternalAxiosRequestConfig } from 'axios';

vi.mock('axios', async () => {
  const actual = await vi.importActual<typeof import('axios')>('axios');
  const createMockAxiosInstance = () => ({
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    patch: vi.fn(),
    interceptors: {
      request: {
        use: vi.fn(),
      },
      response: {
        use: vi.fn(),
      },
    },
  });
  const mockAxios = {
    create: vi.fn(() => createMockAxiosInstance()),
    isAxiosError: vi.fn(),
  };

  return {
    default: mockAxios,
    ...mockAxios,
    AxiosHeaders: actual.AxiosHeaders,
  };
});

vi.mock('./token-manager', () => ({
  default: {
    getAccessToken: vi.fn(),
    getRefreshToken: vi.fn(),
    refreshToken: vi.fn(),
    clearAll: vi.fn(),
  },
}));

import ApiClient, { type ApiError } from './api';
import TokenManager from './token-manager';

const mockedAxios = vi.mocked(axios);

const alphaNumericChars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
const headerValueChars = `${alphaNumericChars} -_/.:`;

const tokenArbitrary = fc.string({ minLength: 20, maxLength: 120 });
const headerNameArbitrary = fc
  .array(fc.constantFrom(...alphaNumericChars.split('')), {
    minLength: 1,
    maxLength: 20,
  })
  .map((chars) => `X-${chars.join('')}`);
const headerValueArbitrary = fc
  .array(fc.constantFrom(...headerValueChars.split('')), {
    minLength: 1,
    maxLength: 60,
  })
  .map((chars) => chars.join(''));
const successResponseArbitrary = fc.record({
  code: fc.constant(200),
  data: fc.anything(),
  message: fc.string({ minLength: 1, maxLength: 100 }),
});
const businessErrorCodeArbitrary = fc
  .integer({ min: 201, max: 599 })
  .filter((code) => code !== 200);
const nonAuthHttpStatusArbitrary = fc.constantFrom(400, 403, 404, 422, 500, 502, 503, 504);

const defaultMessages: Record<number, string> = {
  400: '请求参数错误',
  401: '未授权，请重新登录',
  403: '无权访问',
  404: '请求的资源不存在',
  408: '请求超时',
  500: '服务器错误，请稍后重试',
  502: '网关错误',
  503: '服务暂时不可用',
  504: '网关超时',
};

function buildResponse(data: unknown, config: Partial<InternalAxiosRequestConfig> = {}) {
  return {
    data,
    status: 200,
    statusText: 'OK',
    headers: {},
    config: {
      url: '/test',
      method: 'get',
      headers: new AxiosHeaders(),
      ...config,
    } as InternalAxiosRequestConfig,
  };
}

function buildAxiosError(
  status: number | undefined,
  data: Record<string, unknown> | undefined,
  extras: Partial<AxiosError> = {}
): Partial<AxiosError> {
  if (status === undefined) {
    return {
      request: {},
      config: {} as InternalAxiosRequestConfig,
      isAxiosError: true,
      toJSON: () => ({}),
      name: 'AxiosError',
      message: 'Network Error',
      ...extras,
    };
  }

  return {
    response: {
      status,
      data,
      statusText: 'Error',
      headers: {},
      config: {} as InternalAxiosRequestConfig,
    },
    config: {} as InternalAxiosRequestConfig,
    isAxiosError: true,
    toJSON: () => ({}),
    name: 'AxiosError',
    message: 'Request failed',
    ...extras,
  };
}

function expectedDefaultMessage(status: number): string {
  return defaultMessages[status] ?? `请求失败 (${status})`;
}

describe('HTTP Client - Property-Based Tests', () => {
  let mockAxiosInstance: any;

  beforeEach(() => {
    vi.clearAllMocks();

    mockAxiosInstance = {
      get: vi.fn(),
      post: vi.fn(),
      put: vi.fn(),
      delete: vi.fn(),
      patch: vi.fn(),
      interceptors: {
        request: {
          use: vi.fn((onFulfilled) => {
            mockAxiosInstance._requestInterceptor = onFulfilled;
            return 0;
          }),
        },
        response: {
          use: vi.fn((onFulfilled, onRejected) => {
            mockAxiosInstance._responseInterceptor = onFulfilled;
            mockAxiosInstance._responseErrorInterceptor = onRejected;
            return 0;
          }),
        },
      },
    };

    mockedAxios.create.mockReturnValue(mockAxiosInstance as never);
    new ApiClient('http://localhost:8000');
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('Request Authorization Header Injection', () => {
    it('adds Authorization when an access token exists', () => {
      fc.assert(
        fc.property(tokenArbitrary, (token) => {
          vi.mocked(TokenManager.getAccessToken).mockReturnValue(token);

          const config: InternalAxiosRequestConfig = {
            url: '/test',
            method: 'get',
            headers: new AxiosHeaders(),
          } as InternalAxiosRequestConfig;

          const interceptedConfig = mockAxiosInstance._requestInterceptor(config);

          expect(interceptedConfig.headers.Authorization).toBe(`Bearer ${token}`);
        }),
        { numRuns: 100 }
      );
    });

    it('preserves existing headers when adding Authorization', () => {
      fc.assert(
        fc.property(tokenArbitrary, headerNameArbitrary, headerValueArbitrary, (token, headerName, headerValue) => {
          vi.mocked(TokenManager.getAccessToken).mockReturnValue(token);

          const headers = new AxiosHeaders();
          headers.set(headerName, headerValue);

          const config: InternalAxiosRequestConfig = {
            url: '/test',
            method: 'get',
            headers,
          } as InternalAxiosRequestConfig;

          const interceptedConfig = mockAxiosInstance._requestInterceptor(config);

          expect(interceptedConfig.headers.Authorization).toBe(`Bearer ${token}`);
          expect(interceptedConfig.headers.get(headerName)).toBe(headerValue);
        }),
        { numRuns: 100 }
      );
    });

    it('does not add Authorization when the token is missing', () => {
      fc.assert(
        fc.property(fc.constant(null), () => {
          vi.mocked(TokenManager.getAccessToken).mockReturnValue(null);

          const config: InternalAxiosRequestConfig = {
            url: '/test',
            method: 'get',
            headers: new AxiosHeaders(),
          } as InternalAxiosRequestConfig;

          const interceptedConfig = mockAxiosInstance._requestInterceptor(config);

          expect(interceptedConfig.headers.Authorization).toBeUndefined();
        }),
        { numRuns: 100 }
      );
    });

    it('does not add Authorization for public auth routes', () => {
      vi.mocked(TokenManager.getAccessToken).mockReturnValue('stale-access-token');

      const config: InternalAxiosRequestConfig = {
        url: '/api/auth/login',
        method: 'post',
        headers: new AxiosHeaders(),
      } as InternalAxiosRequestConfig;

      const interceptedConfig = mockAxiosInstance._requestInterceptor(config);

      expect(interceptedConfig.headers.Authorization).toBeUndefined();
    });
  });

  describe('Response Data Extraction', () => {
    it('returns only the data field for successful business responses', () => {
      fc.assert(
        fc.property(successResponseArbitrary, (apiResponse) => {
          const result = mockAxiosInstance._responseInterceptor(buildResponse(apiResponse));
          expect(result).toEqual(apiResponse.data);
        }),
        { numRuns: 100 }
      );
    });

    it('returns blob payloads unchanged', () => {
      fc.assert(
        fc.property(fc.uint8Array(), (bytes) => {
          const blob = new Blob([bytes], { type: 'application/octet-stream' });
          const result = mockAxiosInstance._responseInterceptor(
            buildResponse(blob, { responseType: 'blob' })
          );

          expect(result).toBe(blob);
        }),
        { numRuns: 100 }
      );
    });

    it('rejects when HTTP 200 wraps a business error code', async () => {
      await fc.assert(
        fc.asyncProperty(
          businessErrorCodeArbitrary,
          fc.anything(),
          fc.string({ minLength: 1, maxLength: 100 }),
          async (code, data, message) => {
            const result = mockAxiosInstance._responseInterceptor(
              buildResponse({ code, data, message })
            );

            await expect(result).rejects.toEqual({ code, message });
          }
        ),
        { numRuns: 100 }
      );
    });
  });

  describe('Error Message Formatting', () => {
    it('uses response.message as the primary message for non-422 errors', async () => {
      await fc.assert(
        fc.asyncProperty(
          fc.constantFrom(400, 403, 404, 500, 502, 503, 504),
          fc.string({ minLength: 1, maxLength: 120 }),
          fc.string({ minLength: 1, maxLength: 120 }),
          async (status, message, detail) => {
            const error = buildAxiosError(status, { message, detail });

            await expect(mockAxiosInstance._responseErrorInterceptor(error)).rejects.toMatchObject({
              code: status,
              message,
              detail,
            });
          }
        ),
        { numRuns: 100 }
      );
    });

    it('promotes detail to the primary message for 422 responses', async () => {
      await fc.assert(
        fc.asyncProperty(
          fc.string({ minLength: 1, maxLength: 120 }),
          fc.option(fc.string({ minLength: 1, maxLength: 120 }), { nil: undefined }),
          async (detail, message) => {
            const error = buildAxiosError(422, { message, detail });

            await expect(mockAxiosInstance._responseErrorInterceptor(error)).rejects.toMatchObject({
              code: 422,
              message: detail,
              detail,
            });
          }
        ),
        { numRuns: 100 }
      );
    });

    it('falls back to the built-in status message when response.message is absent', async () => {
      await fc.assert(
        fc.asyncProperty(nonAuthHttpStatusArbitrary, async (status) => {
          const error = buildAxiosError(status, {});

          await expect(mockAxiosInstance._responseErrorInterceptor(error)).rejects.toMatchObject({
            code: status,
            message: expectedDefaultMessage(status),
          });
        }),
        { numRuns: 100 }
      );
    });

    it('formats network errors with code 0 and the network message', async () => {
      await fc.assert(
        fc.asyncProperty(fc.constant(null), async () => {
          const error = buildAxiosError(undefined, undefined);

          await expect(mockAxiosInstance._responseErrorInterceptor(error)).rejects.toMatchObject({
            code: 0,
            message: '网络连接失败，请检查网络设置',
          } satisfies ApiError);
        }),
        { numRuns: 100 }
      );
    });
  });

  describe('Authentication Retry Handling', () => {
    it('does not try to refresh tokens for login 401 responses', async () => {
      vi.mocked(TokenManager.getRefreshToken).mockReturnValue('refresh-token');

      const error = buildAxiosError(
        401,
        { detail: 'Unauthorized' },
        {
          config: {
            url: '/api/auth/login',
            method: 'post',
            headers: new AxiosHeaders(),
          } as InternalAxiosRequestConfig,
        }
      );

      await expect(mockAxiosInstance._responseErrorInterceptor(error)).rejects.toMatchObject({
        code: 401,
        message: 'Unauthorized',
        detail: 'Unauthorized',
      });

      expect(TokenManager.refreshToken).not.toHaveBeenCalled();
      expect(TokenManager.clearAll).not.toHaveBeenCalled();
    });
  });
});
