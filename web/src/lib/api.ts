import axios, { type AxiosRequestConfig } from 'axios';
import TokenManager from './token-manager';

type ImportMetaWithEnv = ImportMeta & {
  env?: {
    VITE_API_BASE_URL?: string;
  };
};

const baseURL = (
  (import.meta as ImportMetaWithEnv).env?.VITE_API_BASE_URL || ''
).replace(/\/+$/, '');

const client = axios.create({
  baseURL,
  timeout: 30_000,
});

const unwrapResponseData = <T>(payload: unknown): T => {
  if (
    payload &&
    typeof payload === 'object' &&
    'data' in payload &&
    ('code' in payload || 'message' in payload)
  ) {
    return (payload as { data: T }).data;
  }

  return payload as T;
};

client.interceptors.request.use((config) => {
  const token = TokenManager.getAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  return config;
});

client.interceptors.response.use(
  (response) => unwrapResponseData(response.data),
  async (error) => {
    const originalRequest = error.config as AxiosRequestConfig & { _retry?: boolean };

    if (error.response?.status === 401 && !originalRequest?._retry) {
      originalRequest._retry = true;

      try {
        const tokenData = await TokenManager.refreshToken();
        originalRequest.headers = {
          ...originalRequest.headers,
          Authorization: `Bearer ${tokenData.access_token}`,
        };
        return client(originalRequest);
      } catch (refreshError) {
        TokenManager.clearAll();
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

export const api = {
  get: <T>(url: string, config?: AxiosRequestConfig): Promise<T> =>
    client.get(url, config) as Promise<T>,
  post: <T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> =>
    client.post(url, data, config) as Promise<T>,
  put: <T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> =>
    client.put(url, data, config) as Promise<T>,
  delete: <T>(url: string, config?: AxiosRequestConfig): Promise<T> =>
    client.delete(url, config) as Promise<T>,
};

export default api;
