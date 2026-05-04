/**
 * Auth Context
 * 全局认证状态管理
 */

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import AuthService, { type LoginParams } from '@/services/auth.service';
import TokenManager, { type UserInfo } from '@/lib/token-manager';

// ==================== 接口定义 ====================

export interface AuthState {
  isAuthenticated: boolean;
  user: UserInfo | null;
  loading: boolean;
}

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
  const [state, setState] = useState<AuthState>({
    isAuthenticated: false,
    user: null,
    loading: true,
  });

  /**
   * 检查认证状态
   */
  const checkAuth = useCallback(async () => {
    try {
      const isAuth = AuthService.isAuthenticated();
      const user = AuthService.getCurrentUser();

      if (!isAuth && TokenManager.getRefreshToken()) {
        try {
          const refreshed = await AuthService.refreshToken();
          setState({
            isAuthenticated: true,
            user: refreshed.user || AuthService.getCurrentUser(),
            loading: false,
          });
          return;
        } catch (refreshError) {
          console.error('[AuthContext] Session restore failed:', refreshError);
          AuthService.logout({ redirect: false });
        }
      }

      setState({
        isAuthenticated: isAuth,
        user: user,
        loading: false,
      });
    } catch (error) {
      console.error('[AuthContext] Check auth failed:', error);
      setState({
        isAuthenticated: false,
        user: null,
        loading: false,
      });
    }
  }, []);

  /**
   * 登录
   */
  const login = useCallback(async (params: LoginParams) => {
    try {
      setState((prev) => ({ ...prev, loading: true }));

      const result = await AuthService.login(params);

      setState({
        isAuthenticated: true,
        user: result.user,
        loading: false,
      });
    } catch (error) {
      setState((prev) => ({
        ...prev,
        loading: false,
      }));
      throw error;
    }
  }, []);

  /**
   * 登出
   */
  const logout = useCallback(() => {
    AuthService.logout({ redirect: false });
    setState({
      isAuthenticated: false,
      user: null,
      loading: false,
    });
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
      setState({
        isAuthenticated: false,
        user: null,
        loading: false,
      });
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
