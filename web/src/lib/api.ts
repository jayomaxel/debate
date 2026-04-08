import axios, {
  AxiosInstance,
  AxiosRequestConfig,
  AxiosResponse,
  AxiosError,
  InternalAxiosRequestConfig,
} from 'axios';
import TokenManager from './token-manager';

interface ApiResponse<T = any> {
  code: number;
  data: T;
  message: string;
}

interface ApiError {
  code: number;
  message: string;
  detail?: string;
}

class ApiClient {
  private instance: AxiosInstance;
  private env: any;
  private isRefreshing = false;
  private failedQueue: Array<{
    resolve: (value?: any) => void;
    reject: (reason?: any) => void;
  }> = [];

  constructor(baseURL?: string) {
    this.env = (import.meta as any).env || {};

    const apiBaseURL =
      baseURL !== undefined ? baseURL : (this.env.VITE_API_BASE_URL ?? '');
    
    this.instance = axios.create({
      baseURL: apiBaseURL,
      timeout: 60000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.setupInterceptors();
  }

  private processQueue(error: any = null) {
    this.failedQueue.forEach((promise) => {
      if (error) {
        promise.reject(error);
      } else {
        promise.resolve();
      }
    });

    this.failedQueue = [];
  }

  private isPublicAuthRequest(url?: string): boolean {
    if (!url) {
      return false;
    }

    const normalizedUrl = url.toLowerCase();
    const publicAuthPaths = [
      '/api/auth/login',
      '/api/auth/refresh',
      '/api/auth/register/teacher',
      '/api/auth/register/student',
      '/api/auth/classes/public',
    ];

    return publicAuthPaths.some((path) => normalizedUrl.includes(path));
  }

  private setupInterceptors() {
    // 请求拦截器 - 添加Authorization header
    this.instance.interceptors.request.use(
      (config: InternalAxiosRequestConfig) => {
        // 从TokenManager获取access_token
        const token = TokenManager.getAccessToken();
        
        if (token && config.headers && !this.isPublicAuthRequest(config.url)) {
          config.headers.Authorization = `Bearer ${token}`;
        }

        // 开发环境日志
        if (this.env.DEV) {
          console.log(`[API Request] ${config.method?.toUpperCase()} ${config.url}`);
        }

        return config;
      },
      (error: AxiosError) => {
        console.error('[API Request Error]', error);
        return Promise.reject(error);
      }
    );

    // 响应拦截器 - 处理响应和错误
    this.instance.interceptors.response.use(
      (response: AxiosResponse<ApiResponse>) => {
        // 如果是blob类型，直接返回data
        if (response.config.responseType === 'blob') {
          return response.data;
        }

        const { code, data, message } = response.data;

        // 开发环境日志
        if (this.env.DEV) {
          console.log(`[API Response] ${response.config.url}`, { code, message });
        }

        // 处理业务错误
        if (code !== 200) {
          const error: ApiError = { code, message };
          return Promise.reject(error);
        }

        // 提取并返回data字段
        return data;
      },
      async (error: AxiosError<any>) => {
        const originalRequest = error.config as InternalAxiosRequestConfig & {
          _retry?: boolean;
        };

        // 处理401未授权错误 - 尝试刷新token
        const shouldRetryWithRefresh = Boolean(
          error.response?.status === 401 &&
          originalRequest &&
          !originalRequest._retry &&
          !this.isPublicAuthRequest(originalRequest.url) &&
          TokenManager.getRefreshToken()
        );

        if (shouldRetryWithRefresh) {
          if (this.isRefreshing) {
            // 如果正在刷新token，将请求加入队列
            return new Promise((resolve, reject) => {
              this.failedQueue.push({ resolve, reject });
            })
              .then(() => {
                return this.instance(originalRequest);
              })
              .catch((err) => {
                return Promise.reject(err);
              });
          }

          originalRequest._retry = true;
          this.isRefreshing = true;

          try {
            // 尝试刷新token
            await TokenManager.refreshToken();
            this.processQueue();
            this.isRefreshing = false;

            // 重试原请求
            return this.instance(originalRequest);
          } catch (refreshError) {
            this.processQueue(refreshError);
            this.isRefreshing = false;
            
            // 刷新失败，清除认证信息并重定向到登录页
            TokenManager.clearAll();
            
            if (typeof window !== 'undefined') {
              window.location.href = '/login';
            }
            
            return Promise.reject(refreshError);
          }
        }

        // 格式化错误信息
        const apiError = this.formatError(error);
        
        // 开发环境日志
        if (this.env.DEV) {
          console.error('[API Error]', apiError);
        }

        return Promise.reject(apiError);
      }
    );
  }

  private formatError(error: AxiosError<any>): ApiError {
    if (error.response) {
      // 服务器返回错误状态码
      const { status, data } = error.response;
      let message = data?.message || '';
      const detail = data?.detail;

      // 处理422验证错误
      if (detail) {
        if (Array.isArray(detail)) {
          if (status === 422 || !message) {
            message = detail.map((d: any) => d.msg || '输入错误').join('; ');
          }
        } else if (typeof detail === 'string') {
          if (status === 422 || !message) {
            message = detail;
          }
        } else {
          if (status === 422 || !message) {
            message = JSON.stringify(detail);
          }
        }
      } else if (!message) {
        message = this.getErrorMessage(status);
      }
      
      return {
        code: status,
        message: typeof message === 'string' ? message : JSON.stringify(message),
        detail: detail
          ? (typeof detail === 'string' ? detail : JSON.stringify(detail))
          : undefined,
      };
    } else if (error.request) {
      // 请求已发出但没有收到响应
      return {
        code: 0,
        message: '网络连接失败，请检查网络设置',
      };
    } else {
      // 请求配置错误
      return {
        code: -1,
        message: error.message || '请求失败',
      };
    }
  }

  private getErrorMessage(status: number): string {
    const errorMessages: Record<number, string> = {
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

    return errorMessages[status] || `请求失败 (${status})`;
  }

  async get<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return this.instance.get(url, config);
  }

  async post<T>(
    url: string,
    data?: any,
    config?: AxiosRequestConfig
  ): Promise<T> {
    return this.instance.post(url, data, config);
  }

  async put<T>(
    url: string,
    data?: any,
    config?: AxiosRequestConfig
  ): Promise<T> {
    return this.instance.put(url, data, config);
  }

  async delete<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return this.instance.delete(url, config);
  }

  async patch<T>(
    url: string,
    data?: any,
    config?: AxiosRequestConfig
  ): Promise<T> {
    return this.instance.patch(url, data, config);
  }

  getInstance(): AxiosInstance {
    return this.instance;
  }
}

// 创建默认实例
export const apiClient = new ApiClient();

// 类型定义
export type { ApiResponse, ApiError };

// 便捷方法
export const api = {
  get: <T>(url: string, config?: AxiosRequestConfig) =>
    apiClient.get<T>(url, config),
  post: <T>(url: string, data?: any, config?: AxiosRequestConfig) =>
    apiClient.post<T>(url, data, config),
  put: <T>(url: string, data?: any, config?: AxiosRequestConfig) =>
    apiClient.put<T>(url, data, config),
  delete: <T>(url: string, config?: AxiosRequestConfig) =>
    apiClient.delete<T>(url, config),
  patch: <T>(url: string, data?: any, config?: AxiosRequestConfig) =>
    apiClient.patch<T>(url, data, config),
};

export default ApiClient;
