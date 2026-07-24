/**
 * Auth Context
 * 全局认证状态管理
 */

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import AuthService, { type LoginParams } from '@/services/auth.service';
import TokenManager, { type UserInfo } from '@/lib/token-manager';
import { toAuthStateShape } from '@/lib/frontend-adapters';
import type { FrontendAuthStateShape } from '@/lib/frontend-contracts';

// ==================== 接口定义 ====================

export type AuthState = FrontendAuthStateShape<UserInfo>;

export interface AuthActions {
  login: (params: LoginParams) => Promise<void>;
  logout: () => void;
  updateUser: (user: Partial<UserInfo>) => void;
  checkAuth: () => Promise<void>;
}

type AuthContextType = AuthState & AuthActions;

// ==================== Context ====================

const AuthContext = createContext<AuthContextType | null>(null);

// ==================== Provider ====================

interface AuthProviderProps {
  children: React.ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [state, setState] = useState<AuthState>(() =>
    toAuthStateShape<UserInfo>({ status: 'initializing' })
  );

  /**
   * 检查认证状态
   */
  const checkAuth = useCallback(async () => {
    setState(toAuthStateShape<UserInfo>({ status: 'initializing' }));
    try {
      const refreshToken = TokenManager.getRefreshToken();
      if (refreshToken) {
        try {
          const refreshed = await AuthService.refreshToken();
          setState(toAuthStateShape({
            status: 'authenticated',
            isAuthenticated: true,
            user: refreshed.user || AuthService.getCurrentUser(),
          }));
          return;
        } catch (refreshError) {
          console.error('[AuthContext] Session restore failed:', refreshError);
          AuthService.logout({ redirect: false });
          setState(toAuthStateShape<UserInfo>({ status: 'expired' }));
          return;
        }
      }

      const isAuth = AuthService.isAuthenticated();
      const user = AuthService.getCurrentUser();

      setState(toAuthStateShape({
        status: isAuth && user ? 'authenticated' : 'anonymous',
        isAuthenticated: isAuth,
        user: user,
      }));
    } catch (error) {
      console.error('[AuthContext] Check auth failed:', error);
      setState(toAuthStateShape<UserInfo>({
        status: 'error',
        error: error instanceof Error ? error.message : '认证状态检查失败',
      }));
    }
  }, []);

  /**
   * 登录
   */
  const login = useCallback(async (params: LoginParams) => {
    try {
      setState(toAuthStateShape<UserInfo>({ status: 'initializing' }));

      const result = await AuthService.login(params);

      setState(toAuthStateShape({
        status: 'authenticated',
        isAuthenticated: true,
        user: result.user,
      }));
    } catch (error) {
      setState(toAuthStateShape<UserInfo>({
        status: 'error',
        error: error instanceof Error ? error.message : '登录失败',
      }));
      throw error;
    }
  }, []);

  /**
   * 登出
   */
  const logout = useCallback(() => {
    AuthService.logout({ redirect: false });
    setState(toAuthStateShape<UserInfo>({ status: 'anonymous' }));
  }, []);

  /**
   * 更新用户信息
   */
  const updateUser = useCallback((updatedUser: Partial<UserInfo>) => {
    setState((prev) => {
      if (!prev.user) {
        return prev;
      }

      const newUser = { ...prev.user, ...updatedUser };
      
      // 同步更新到localStorage
      TokenManager.setUserInfo(newUser);

      return {
        ...prev,
        user: newUser,
      };
    });
  }, []);

  /**
   * 初始化时从localStorage恢复状态
   */
  useEffect(() => {
    void checkAuth();
  }, [checkAuth]);

  /**
   * 监听storage事件，同步多标签页状态
   */
  useEffect(() => {
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'user_info' || e.key === 'access_token') {
        void checkAuth();
      }
    };

    const handleAuthExpired = () => {
      setState(toAuthStateShape<UserInfo>({ status: 'expired' }));
    };

    window.addEventListener('storage', handleStorageChange);
    window.addEventListener('auth:expired', handleAuthExpired);

    return () => {
      window.removeEventListener('storage', handleStorageChange);
      window.removeEventListener('auth:expired', handleAuthExpired);
    };
  }, [checkAuth]);

  const value: AuthContextType = {
    ...state,
    login,
    logout,
    updateUser,
    checkAuth,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// ==================== Hook ====================

/**
 * useAuth Hook
 * 在组件中使用认证状态和方法
 */
export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }

  return context;
}

export default AuthContext;
