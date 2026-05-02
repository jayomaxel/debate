import axios from 'axios';

export interface TokenData {
  access_token: string;
  refresh_token: string;
  token_type?: string;
  expires_in?: number;
  user?: UserInfo;
}

export interface UserInfo {
  id: string;
  account: string;
  name: string;
  user_type: 'teacher' | 'student' | 'administrator' | string;
  email?: string | null;
  phone?: string | null;
  student_id?: string | null;
  class_id?: string | null;
  avatar?: string | null;
  avatar_url?: string | null;
  avatar_mode?: 'custom' | 'default' | 'none' | string;
  avatar_default_key?: string | null;
  [key: string]: unknown;
}

const ACCESS_TOKEN_KEY = 'access_token';
const REFRESH_TOKEN_KEY = 'refresh_token';
const TOKEN_TYPE_KEY = 'token_type';
const TOKEN_EXPIRES_AT_KEY = 'token_expires_at';
const USER_INFO_KEY = 'user_info';

type ImportMetaWithEnv = ImportMeta & {
  env?: {
    VITE_API_BASE_URL?: string;
  };
};

const getApiBaseUrl = () => {
  const envBase = (
    (import.meta as ImportMetaWithEnv).env?.VITE_API_BASE_URL || ''
  ).replace(/\/+$/, '');
  return envBase;
};

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

const storageAvailable = () => typeof localStorage !== 'undefined';

class TokenManager {
  static setTokens(tokenData: TokenData): void {
    if (!storageAvailable()) {
      return;
    }

    localStorage.setItem(ACCESS_TOKEN_KEY, tokenData.access_token);
    localStorage.setItem(REFRESH_TOKEN_KEY, tokenData.refresh_token);
    localStorage.setItem(TOKEN_TYPE_KEY, tokenData.token_type || 'bearer');

    if (tokenData.expires_in) {
      const expiresAt = Date.now() + tokenData.expires_in * 1000;
      localStorage.setItem(TOKEN_EXPIRES_AT_KEY, String(expiresAt));
    }
  }

  static getAccessToken(): string | null {
    if (!storageAvailable()) {
      return null;
    }

    return localStorage.getItem(ACCESS_TOKEN_KEY);
  }

  static getRefreshToken(): string | null {
    if (!storageAvailable()) {
      return null;
    }

    return localStorage.getItem(REFRESH_TOKEN_KEY);
  }

  static getTokenType(): string {
    if (!storageAvailable()) {
      return 'bearer';
    }

    return localStorage.getItem(TOKEN_TYPE_KEY) || 'bearer';
  }

  static isTokenExpired(): boolean {
    if (!storageAvailable()) {
      return true;
    }

    const expiresAt = Number(localStorage.getItem(TOKEN_EXPIRES_AT_KEY) || '0');
    if (!expiresAt) {
      return false;
    }

    return Date.now() >= expiresAt - 30_000;
  }

  static setUserInfo(userInfo: UserInfo): void {
    if (!storageAvailable()) {
      return;
    }

    localStorage.setItem(USER_INFO_KEY, JSON.stringify(userInfo));
  }

  static getUserInfo(): UserInfo | null {
    if (!storageAvailable()) {
      return null;
    }

    const raw = localStorage.getItem(USER_INFO_KEY);
    if (!raw) {
      return null;
    }

    try {
      return JSON.parse(raw) as UserInfo;
    } catch {
      localStorage.removeItem(USER_INFO_KEY);
      return null;
    }
  }

  static clearAll(): void {
    if (!storageAvailable()) {
      return;
    }

    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    localStorage.removeItem(TOKEN_TYPE_KEY);
    localStorage.removeItem(TOKEN_EXPIRES_AT_KEY);
    localStorage.removeItem(USER_INFO_KEY);
  }

  static async refreshToken(): Promise<TokenData> {
    const refreshToken = this.getRefreshToken();
    if (!refreshToken) {
      throw new Error('No refresh token available');
    }

    const response = await axios.post(`${getApiBaseUrl()}/api/auth/refresh`, {
      refresh_token: refreshToken,
    });
    const tokenData = unwrapResponseData<TokenData>(response.data);
    this.setTokens(tokenData);
    if (tokenData.user) {
      this.setUserInfo(tokenData.user);
    }
    return tokenData;
  }
}

export default TokenManager;
