/**
 * Auth Service
 * 认证服务 - 处理用户登录、注册、登出等认证相关操作
 */

import { api } from '../lib/api';
import TokenManager, { type TokenData, type UserInfo } from '../lib/token-manager';

// ==================== 接口定义 ====================

export interface TeacherRegisterParams {
  account: string;  // 教工号
  email: string;
  phone: string;
  password: string;
  name: string;
}

export interface StudentRegisterParams {
  account: string;
  password: string;
  name: string;
  class_id?: string;  // 班级ID（可选）
  email?: string;
  student_id?: string;
}

export interface LoginParams {
  account: string;
  password: string;
  user_type: 'teacher' | 'student' | 'administrator';
}

export interface LoginResult {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: UserInfo;
}

export interface ChangePasswordParams {
  old_password: string;
  new_password: string;
}

export interface DeleteAccountParams {
  password: string;
}

export interface DeleteAccountResult {
  data_retained: boolean;
  note: string;
}

// ==================== Auth Service ====================

class AuthService {
  /**
   * 教师注册
   */
  static async registerTeacher(params: TeacherRegisterParams): Promise<UserInfo> {
    try {
      const response = await api.post<UserInfo>('/api/auth/register/teacher', params);
      return response;
    } catch (error) {
      console.error('[AuthService] Teacher registration failed:', error);
      throw error;
    }
  }

  /**
   * 学生注册
   */
  static async registerStudent(params: StudentRegisterParams): Promise<UserInfo> {
    try {
      const response = await api.post<UserInfo>('/api/auth/register/student', params);
      return response;
    } catch (error) {
      console.error('[AuthService] Student registration failed:', error);
      throw error;
    }
  }

  /**
   * 用户登录
   */
  static async login(params: LoginParams): Promise<LoginResult> {
    try {
      const response = await api.post<LoginResult>('/api/auth/login', params);

      // 存储tokens
      const tokenData: TokenData = {
        access_token: response.access_token,
        refresh_token: response.refresh_token,
        token_type: response.token_type,
        expires_in: response.expires_in,
      };
      TokenManager.setTokens(tokenData);

      // 存储用户信息
      TokenManager.setUserInfo(response.user);

      return response;
    } catch (error) {
      console.error('[AuthService] Login failed:', error);
      throw error;
    }
  }

  /**
   * 用户登出
   */
  static logout(): void {
    try {
      // 清除所有认证数据
      TokenManager.clearAll();

      // 重定向到登录页
      if (typeof window !== 'undefined') {
        window.location.href = '/login';
      }
    } catch (error) {
      console.error('[AuthService] Logout failed:', error);
    }
  }

  /**
   * 修改密码
   */
  static async changePassword(params: ChangePasswordParams): Promise<void> {
    try {
      await api.post<void>('/api/auth/change-password', params);
    } catch (error) {
      console.error('[AuthService] Change password failed:', error);
      throw error;
    }
  }

  /**
   * 注销账户
   */
  static async deleteAccount(params: DeleteAccountParams): Promise<DeleteAccountResult> {
    try {
      const response = await api.post<DeleteAccountResult>('/api/auth/delete-account', params);
      
      // 注销成功后清除认证数据
      TokenManager.clearAll();
      
      return response;
    } catch (error) {
      console.error('[AuthService] Delete account failed:', error);
      throw error;
    }
  }

  /**
   * 检查是否已登录
   */
  static isAuthenticated(): boolean {
    const token = TokenManager.getAccessToken();
    const user = TokenManager.getUserInfo();
    
    if (!token || !user) {
      return false;
    }

    // 检查token是否过期
    if (TokenManager.isTokenExpired()) {
      return false;
    }

    return true;
  }

  /**
   * 获取当前用户信息
   */
  static getCurrentUser(): UserInfo | null {
    return TokenManager.getUserInfo();
  }

  /**
   * 刷新token
   */
  static async refreshToken(): Promise<TokenData> {
    try {
      return await TokenManager.refreshToken();
    } catch (error) {
      console.error('[AuthService] Refresh token failed:', error);
      throw error;
    }
  }

  /**
   * 获取班级列表（公开接口，用于注册）
   */
  static async getPublicClasses(): Promise<Array<{
    id: string;
    name: string;
    code: string;
    teacher_name: string;
    student_count: number;
  }>> {
    try {
      return await api.get('/api/auth/classes/public');
    } catch (error) {
      console.error('[AuthService] Get public classes failed:', error);
      throw error;
    }
  }

  /**
   * 获取个人信息
   */
  static async getProfile(): Promise<UserInfo> {
    try {
      return await api.get('/api/auth/profile');
    } catch (error) {
      console.error('[AuthService] Get profile failed:', error);
      throw error;
    }
  }

  /**
   * 更新个人信息
   */
  static async updateProfile(params: {
    name?: string;
    email?: string;
    phone?: string;
    student_id?: string;
    class_id?: string;  // 新增：班级ID
  }): Promise<UserInfo> {
    try {
      return await api.put('/api/auth/profile', params);
    } catch (error) {
      console.error('[AuthService] Update profile failed:', error);
      throw error;
    }
  }
}

export default AuthService;
