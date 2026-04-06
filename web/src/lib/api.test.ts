/**
 * Property-Based Tests for HTTP Client
 * 
 * Feature: frontend-backend-integration
 * Tests Properties 1, 2, and 3 from the design document
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import * as fc from 'fast-check';

// Import AxiosHeaders from the real axios module
import { AxiosHeaders } from 'axios';
import type { AxiosError, InternalAxiosRequestConfig } from 'axios';

// Mock axios BEFORE importing ApiClient
vi.mock('axios', async () => {
  // Import the actual axios to get AxiosHeaders
  const actual = await vi.importActual<typeof import('axios')>('axios');
  
  const createMockAxiosInstance = () => ({
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    patch: vi.fn(),
    interceptors: {
      request: {
        use: vi.fn((onFulfilled) => {
          return 0;
        }),
      },
      response: {
        use: vi.fn((onFulfilled, onRejected) => {
          return 0;
        }),
      },
    },
  });
  
  const mockInstance = createMockAxiosInstance();
  const mockAxios = {
    create: vi.fn(() => mockInstance),
    isAxiosError: vi.fn(),
  };
  
  return {
    default: mockAxios,
    ...mockAxios,
    // Export AxiosHeaders from the actual axios
    AxiosHeaders: actual.AxiosHeaders,
  };
});

vi.mock('./token-manager', () => ({
  default: {
    getAccessToken: vi.fn(),
    refreshToken: vi.fn(),
    clearAll: vi.fn(),
  },
}));

// Import AFTER mocking
import axios from 'axios';
import ApiClient, { ApiResponse, ApiError } from './api';
import TokenManager from './token-manager';

const mockedAxios = vi.mocked(axios, true);

// Arbitraries (generators) for property-based testing
const tokenArbitrary = fc.string({ minLength: 20, maxLength: 200 });

const apiResponseArbitrary = <T>(dataArbitrary: fc.Arbitrary<T>) =>
  fc.record({
    code: fc.constant(200),
    data: dataArbitrary,
    message: fc.string({ minLength: 1, maxLength: 100 }),
  });

const httpStatusCodeArbitrary = fc.oneof(
  fc.constant(400),
  fc.constant(401),
  fc.constant(403),
  fc.constant(404),
  fc.constant(500),
  fc.constant(502),
  fc.constant(503)
);

const errorResponseArbitrary = fc.record({
  status: httpStatusCodeArbitrary,
  data: fc.record({
    detail: fc.option(fc.string({ minLength: 1, maxLength: 200 }), { nil: undefined }),
    message: fc.option(fc.string({ minLength: 1, maxLength: 200 }), { nil: undefined }),
  }),
});

describe('HTTP Client - Property-Based Tests', () => {
  let apiClient: ApiClient;
  let mockAxiosInstance: any;

  beforeEach(() => {
    // Clear all mocks
    vi.clearAllMocks();

    // Create mock axios instance
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

    // Mock axios.create to return our mock instance
    mockedAxios.create.mockReturnValue(mockAxiosInstance as any);

    // Create API client instance
    apiClient = new ApiClient('http://localhost:8000');
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('Property 1: Request Authorization Header Injection', () => {
    /**
     * **Validates: Requirements 1.5**
     * 
     * Property: For any HTTP request when an access token exists in TokenManager,
     * the request interceptor should automatically add an `Authorization: Bearer {token}`
     * header to the request.
     */
    it('should add Authorization header with Bearer token for any valid token', () => {
      fc.assert(
        fc.property(tokenArbitrary, (token) => {
          // Arrange: Mock TokenManager to return the token
          vi.mocked(TokenManager.getAccessToken).mockReturnValue(token);

          // Create a mock request config
          const mockConfig: InternalAxiosRequestConfig = {
            url: '/test',
            method: 'get',
            headers: new AxiosHeaders(),
          } as InternalAxiosRequestConfig;

          // Act: Call the request interceptor
          const interceptedConfig = mockAxiosInstance._requestInterceptor(mockConfig);

          // Assert: Authorization header should be added with Bearer token
          expect(interceptedConfig.headers.Authorization).toBe(`Bearer ${token}`);
        }),
        { numRuns: 100 }
      );
    });

    it('should not add Authorization header when token does not exist', () => {
      fc.assert(
        fc.property(fc.constant(null), () => {
          // Arrange: Mock TokenManager to return null
          vi.mocked(TokenManager.getAccessToken).mockReturnValue(null);

          // Create a mock request config
          const mockConfig: InternalAxiosRequestConfig = {
            url: '/test',
            method: 'get',
            headers: new AxiosHeaders(),
          } as InternalAxiosRequestConfig;

          // Act: Call the request interceptor
          const interceptedConfig = mockAxiosInstance._requestInterceptor(mockConfig);

          // Assert: Authorization header should not be added
          expect(interceptedConfig.headers.Authorization).toBeUndefined();
        }),
        { numRuns: 100 }
      );
    });

    it('should add Authorization header for any HTTP method', () => {
      fc.assert(
        fc.property(
          tokenArbitrary,
          fc.constantFrom('get', 'post', 'put', 'delete', 'patch'),
          (token, method) => {
            // Arrange: Mock TokenManager to return the token
            vi.mocked(TokenManager.getAccessToken).mockReturnValue(token);

            // Create a mock request config
            const mockConfig: InternalAxiosRequestConfig = {
              url: '/test',
              method,
              headers: new AxiosHeaders(),
            } as InternalAxiosRequestConfig;

            // Act: Call the request interceptor
            const interceptedConfig = mockAxiosInstance._requestInterceptor(mockConfig);

            // Assert: Authorization header should be added regardless of method
            expect(interceptedConfig.headers.Authorization).toBe(`Bearer ${token}`);
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should preserve existing headers when adding Authorization', () => {
      fc.assert(
        fc.property(
          tokenArbitrary,
          fc.string({ minLength: 1, maxLength: 50 }),
          fc.string({ minLength: 1, maxLength: 100 }),
          (token, headerName, headerValue) => {
            // Arrange: Mock TokenManager to return the token
            vi.mocked(TokenManager.getAccessToken).mockReturnValue(token);

            // Create a mock request config with existing headers
            const headers = new AxiosHeaders();
            headers.set(headerName, headerValue);
            
            const mockConfig: InternalAxiosRequestConfig = {
              url: '/test',
              method: 'get',
              headers,
            } as InternalAxiosRequestConfig;

            // Act: Call the request interceptor
            const interceptedConfig = mockAxiosInstance._requestInterceptor(mockConfig);

            // Assert: Both Authorization and existing headers should be present
            expect(interceptedConfig.headers.Authorization).toBe(`Bearer ${token}`);
            expect(interceptedConfig.headers.get(headerName)).toBe(headerValue);
          }
        ),
        { numRuns: 100 }
      );
    });
  });

  describe('Property 2: Response Data Extraction', () => {
    /**
     * **Validates: Requirements 1.7**
     * 
     * Property: For any successful API response with format `{code: 200, data: T, message: string}`,
     * the response interceptor should extract and return only the `data` field.
     */
    it('should extract and return only the data field for any successful response', () => {
      fc.assert(
        fc.property(
          apiResponseArbitrary(fc.anything()),
          (apiResponse) => {
            // Create a mock axios response
            const mockResponse = {
              data: apiResponse,
              status: 200,
              statusText: 'OK',
              headers: {},
              config: {} as InternalAxiosRequestConfig,
            };

            // Act: Call the response interceptor
            const result = mockAxiosInstance._responseInterceptor(mockResponse);

            // Assert: Should return only the data field
            expect(result).toEqual(apiResponse.data);
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should extract data field for various data types', () => {
      fc.assert(
        fc.property(
          fc.oneof(
            apiResponseArbitrary(fc.string()),
            apiResponseArbitrary(fc.integer()),
            apiResponseArbitrary(fc.boolean()),
            apiResponseArbitrary(fc.array(fc.anything())),
            apiResponseArbitrary(fc.object()),
            apiResponseArbitrary(fc.constant(null))
          ),
          (apiResponse) => {
            // Create a mock axios response
            const mockResponse = {
              data: apiResponse,
              status: 200,
              statusText: 'OK',
              headers: {},
              config: {} as InternalAxiosRequestConfig,
            };

            // Act: Call the response interceptor
            const result = mockAxiosInstance._responseInterceptor(mockResponse);

            // Assert: Should return only the data field, preserving its type
            expect(result).toEqual(apiResponse.data);
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should reject when code is not 200 even if HTTP status is 200', () => {
      fc.assert(
        fc.property(
          fc.integer({ min: 201, max: 599 }).filter(code => code !== 200),
          fc.anything(),
          fc.string({ minLength: 1, maxLength: 100 }),
          (code, data, message) => {
            // Create a mock axios response with non-200 code
            const mockResponse = {
              data: { code, data, message },
              status: 200,
              statusText: 'OK',
              headers: {},
              config: {} as InternalAxiosRequestConfig,
            };

            // Act & Assert: Should return a rejected promise with ApiError
            const result = mockAxiosInstance._responseInterceptor(mockResponse);
            
            // The interceptor returns a rejected promise, not throws
            expect(result).toBeInstanceOf(Promise);
            
            // Verify the rejection contains the correct error
            return result.catch((error: ApiError) => {
              expect(error.code).toBe(code);
              expect(error.message).toBe(message);
            });
          }
        ),
        { numRuns: 100 }
      );
    });
  });

  describe('Property 3: Error Message Formatting', () => {
    /**
     * **Validates: Requirements 1.8**
     * 
     * Property: For any failed API response, the error handler should extract the error
     * message and format it into a user-friendly ApiError object with code and message fields.
     */
    it('should format error with code and message for any HTTP error response', async () => {
      await fc.assert(
        fc.asyncProperty(errorResponseArbitrary, async (errorResponse) => {
          // Create a mock axios error
          const mockError: Partial<AxiosError> = {
            response: {
              status: errorResponse.status,
              data: errorResponse.data,
              statusText: 'Error',
              headers: {},
              config: {} as InternalAxiosRequestConfig,
            },
            config: {} as InternalAxiosRequestConfig,
            isAxiosError: true,
            toJSON: () => ({}),
            name: 'AxiosError',
            message: 'Request failed',
          };

          // Act: Call the response error interceptor
          try {
            await mockAxiosInstance._responseErrorInterceptor(mockError);
            // If we reach here, the test should fail (unless it's a 401 with successful refresh)
            if (errorResponse.status !== 401) {
              expect(true).toBe(false);
            }
          } catch (error) {
            const apiError = error as ApiError;

            // Assert: Should have code and message fields
            expect(apiError).toHaveProperty('code');
            expect(apiError).toHaveProperty('message');
            expect(apiError.code).toBe(errorResponse.status);
            expect(typeof apiError.message).toBe('string');
            expect(apiError.message.length).toBeGreaterThan(0);

            // If detail or message exists in response, it should be used
            if (errorResponse.data.detail || errorResponse.data.message) {
              const expectedMessage = errorResponse.data.detail || errorResponse.data.message;
              expect(apiError.message).toBe(expectedMessage);
            }
          }
        }),
        { numRuns: 100 }
      );
    });

    it('should format network error with appropriate message', async () => {
      await fc.assert(
        fc.asyncProperty(fc.constant(null), async () => {
          // Create a mock network error (no response)
          const mockError: Partial<AxiosError> = {
            request: {},
            config: {} as InternalAxiosRequestConfig,
            isAxiosError: true,
            toJSON: () => ({}),
            name: 'AxiosError',
            message: 'Network Error',
          };

          // Act: Call the response error interceptor
          try {
            await mockAxiosInstance._responseErrorInterceptor(mockError);
            expect(true).toBe(false);
          } catch (error) {
            const apiError = error as ApiError;

            // Assert: Should have code 0 and network error message
            expect(apiError.code).toBe(0);
            expect(apiError.message).toBe('网络连接失败，请检查网络设置');
          }
        }),
        { numRuns: 100 }
      );
    });

    it('should provide default error messages for standard HTTP status codes', async () => {
      await fc.assert(
        fc.asyncProperty(
          fc.constantFrom(400, 403, 404, 408, 500, 502, 503, 504),
          async (statusCode) => {
            // Create a mock axios error without detail/message in data
            const mockError: Partial<AxiosError> = {
              response: {
                status: statusCode,
                data: {},
                statusText: 'Error',
                headers: {},
                config: {} as InternalAxiosRequestConfig,
              },
              config: {} as InternalAxiosRequestConfig,
              isAxiosError: true,
              toJSON: () => ({}),
              name: 'AxiosError',
              message: 'Request failed',
            };

            // Expected default messages
            const defaultMessages: Record<number, string> = {
              400: '请求参数错误',
              403: '无权访问',
              404: '请求的资源不存在',
              408: '请求超时',
              500: '服务器错误，请稍后重试',
              502: '网关错误',
              503: '服务暂时不可用',
              504: '网关超时',
            };

            // Act: Call the response error interceptor
            try {
              await mockAxiosInstance._responseErrorInterceptor(mockError);
              // 401 might trigger refresh logic, so we skip assertion for it
              if (statusCode !== 401) {
                expect(true).toBe(false);
              }
            } catch (error) {
              const apiError = error as ApiError;

              // Assert: Should use default message for the status code
              expect(apiError.code).toBe(statusCode);
              expect(apiError.message).toBe(defaultMessages[statusCode]);
            }
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should preserve detail field when present in error response', async () => {
      await fc.assert(
        fc.asyncProperty(
          httpStatusCodeArbitrary.filter(code => code !== 401),
          fc.string({ minLength: 1, maxLength: 200 }),
          fc.string({ minLength: 1, maxLength: 200 }),
          async (statusCode, message, detail) => {
            // Create a mock axios error with detail
            const mockError: Partial<AxiosError> = {
              response: {
                status: statusCode,
                data: { message, detail },
                statusText: 'Error',
                headers: {},
                config: {} as InternalAxiosRequestConfig,
              },
              config: {} as InternalAxiosRequestConfig,
              isAxiosError: true,
              toJSON: () => ({}),
              name: 'AxiosError',
              message: 'Request failed',
            };

            // Act: Call the response error interceptor
            try {
              await mockAxiosInstance._responseErrorInterceptor(mockError);
              expect(true).toBe(false);
            } catch (error) {
              const apiError = error as ApiError;

              // Assert: Should preserve detail field
              expect(apiError.detail).toBe(detail);
              // Detail takes precedence over message in the main message field
              expect(apiError.message).toBe(detail);
            }
          }
        ),
        { numRuns: 100 }
      );
    });
  });

  describe('Edge Cases and Integration', () => {
    it('should handle empty response data gracefully', () => {
      fc.assert(
        fc.property(fc.constant(null), () => {
          // Create a mock response with empty data
          const mockResponse = {
            data: { code: 200, data: null, message: 'Success' },
            status: 200,
            statusText: 'OK',
            headers: {},
            config: {} as InternalAxiosRequestConfig,
          };

          // Act: Call the response interceptor
          const result = mockAxiosInstance._responseInterceptor(mockResponse);

          // Assert: Should return null
          expect(result).toBeNull();
        }),
        { numRuns: 100 }
      );
    });

    it('should handle undefined data field', () => {
      fc.assert(
        fc.property(fc.constant(undefined), () => {
          // Create a mock response with undefined data
          const mockResponse = {
            data: { code: 200, data: undefined, message: 'Success' },
            status: 200,
            statusText: 'OK',
            headers: {},
            config: {} as InternalAxiosRequestConfig,
          };

          // Act: Call the response interceptor
          const result = mockAxiosInstance._responseInterceptor(mockResponse);

          // Assert: Should return undefined
          expect(result).toBeUndefined();
        }),
        { numRuns: 100 }
      );
    });

    it('should handle complex nested data structures', () => {
      fc.assert(
        fc.property(
          apiResponseArbitrary(
            fc.record({
              users: fc.array(
                fc.record({
                  id: fc.uuid(),
                  name: fc.string(),
                  metadata: fc.object(),
                })
              ),
              pagination: fc.record({
                total: fc.integer({ min: 0 }),
                page: fc.integer({ min: 1 }),
                pageSize: fc.integer({ min: 1, max: 100 }),
              }),
            })
          ),
          (apiResponse) => {
            // Create a mock response with complex nested data
            const mockResponse = {
              data: apiResponse,
              status: 200,
              statusText: 'OK',
              headers: {},
              config: {} as InternalAxiosRequestConfig,
            };

            // Act: Call the response interceptor
            const result = mockAxiosInstance._responseInterceptor(mockResponse);

            // Assert: Should preserve complex structure
            expect(result).toEqual(apiResponse.data);
          }
        ),
        { numRuns: 100 }
      );
    });
  });
});
