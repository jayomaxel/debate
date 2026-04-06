/**
 * Token Manager
 * 管理JWT令牌的存储、获取、刷新和清除
 */

export interface TokenData {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface UserInfo {
  id: string;
  account: string;
  name: string;
  email: string;
  user_type: 'teacher' | 'student' | 'administrator';
  avatar?: string;
  phone?: string;
  student_id?: string;
  class_id?: string;
  created_at?: string;
}

// LocalStorage键名常量
const STORAGE_KEYS = {
  ACCESS_TOKEN: 'access_token',
  REFRESH_TOKEN: 'refresh_token',
  TOKEN_EXPIRES_AT: 'token_expires_at',
  USER_INFO: 'user_info',
} as const;

class TokenManager {
  /**
   * 存储token数据
   */
  static setTokens(tokenData: TokenData): void {
    try {
      localStorage.setItem(STORAGE_KEYS.ACCESS_TOKEN, tokenData.access_token);
      localStorage.setItem(STORAGE_KEYS.REFRESH_TOKEN, tokenData.refresh_token);
      
      // 计算过期时间戳（当前时间 + expires_in秒）
      const expiresAt = Date.now() + tokenData.expires_in * 1000;
      localStorage.setItem(STORAGE_KEYS.TOKEN_EXPIRES_AT, expiresAt.toString());
    } catch (error) {
      console.error('Failed to store tokens:', error);
      throw new Error('无法存储认证信息');
    }
  }

  /**
   * 获取access token
   */
  static getAccessToken(): string | null {
    try {
      return localStorage.getItem(STORAGE_KEYS.ACCESS_TOKEN);
    } catch (error) {
      console.error('Failed to get access token:', error);
      return null;
    }
  }

  /**
   * 获取refresh token
   */
  static getRefreshToken(): string | null {
    try {
      return localStorage.getItem(STORAGE_KEYS.REFRESH_TOKEN);
    } catch (error) {
      console.error('Failed to get refresh token:', error);
      return null;
    }
  }

  /**
   * 刷新token
   */
  static async refreshToken(): Promise<TokenData> {
    const refreshToken = this.getRefreshToken();
    
    if (!refreshToken) {
      throw new Error('No refresh token available');
    }

    try {
      // 动态导入api模块避免循环依赖
      const { api } = await import('./api');
      
      const response = await api.post<TokenData>('/api/auth/refresh', {
        refresh_token: refreshToken,
      });

      // 存储新的tokens
      this.setTokens(response);
      
      return response;
    } catch (error) {
      // 刷新失败，清除所有token
      this.clearTokens();
      this.clearUserInfo();
      
      // 重定向到登录页
      if (typeof window !== 'undefined') {
        window.location.href = '/login';
      }
      
      throw new Error('Token refresh failed');
    }
  }

  /**
   * 清除所有token
   */
  static clearTokens(): void {
    try {
      localStorage.removeItem(STORAGE_KEYS.ACCESS_TOKEN);
      localStorage.removeItem(STORAGE_KEYS.REFRESH_TOKEN);
      localStorage.removeItem(STORAGE_KEYS.TOKEN_EXPIRES_AT);
    } catch (error) {
      console.error('Failed to clear tokens:', error);
    }
  }

  /**
   * 检查token是否过期
   */
  static isTokenExpired(): boolean {
    try {
      const expiresAt = localStorage.getItem(STORAGE_KEYS.TOKEN_EXPIRES_AT);
      
      if (!expiresAt) {
        return true;
      }

      const expiresAtTimestamp = parseInt(expiresAt, 10);
      
      // 提前5分钟判定为过期，留出刷新时间
      const bufferTime = 5 * 60 * 1000; // 5分钟
      return Date.now() >= expiresAtTimestamp - bufferTime;
    } catch (error) {
      console.error('Failed to check token expiration:', error);
      return true;
    }
  }

  /**
   * 存储用户信息
   */
  static setUserInfo(userInfo: UserInfo): void {
    try {
      localStorage.setItem(STORAGE_KEYS.USER_INFO, JSON.stringify(userInfo));
    } catch (error) {
      console.error('Failed to store user info:', error);
      throw new Error('无法存储用户信息');
    }
  }

  /**
   * 获取用户信息
   */
  static getUserInfo(): UserInfo | null {
    try {
      const userInfoStr = localStorage.getItem(STORAGE_KEYS.USER_INFO);
      
      if (!userInfoStr) {
        return null;
      }

      return JSON.parse(userInfoStr) as UserInfo;
    } catch (error) {
      console.error('Failed to get user info:', error);
      return null;
    }
  }

  /**
   * 清除用户信息
   */
  static clearUserInfo(): void {
    try {
      localStorage.removeItem(STORAGE_KEYS.USER_INFO);
    } catch (error) {
      console.error('Failed to clear user info:', error);
    }
  }

  /**
   * 清除所有认证数据
   */
  static clearAll(): void {
    this.clearTokens();
    this.clearUserInfo();
  }
}

export default TokenManager;
