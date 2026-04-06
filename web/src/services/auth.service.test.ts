/**
 * Unit Tests for Auth Service
 * 
 * Feature: frontend-backend-integration
 * Tests authentication service methods
 * 
 * **Validates: Requirements 2.1, 2.2, 2.3, 2.7, 2.8**
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import AuthService, {
  type TeacherRegisterParams,
  type StudentRegisterParams,
  type LoginParams,
  type ChangePasswordParams,
  type DeleteAccountParams,
} from './auth.service';
import TokenManager, { type TokenData, type UserInfo } from '../lib/token-manager';
import { api } from '../lib/api';

// Mock dependencies
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
    isTokenExpired: vi.fn(),
    refreshToken: vi.fn(),
  },
}));

describe('Auth Service - Unit Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Reset all mock implementations
    vi.mocked(TokenManager.clearAll).mockImplementation(() => {});
    // Mock window.location for logout tests
    delete (window as any).location;
    (window as any).location = { href: '' };
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('registerTeacher()', () => {
    /**
     * Test: registerTeacher() should call POST /api/auth/register/teacher
     * **Validates: Requirements 2.1**
     */
    it('should call POST /api/auth/register/teacher with correct parameters', async () => {
      // Arrange
      const params: TeacherRegisterParams = {
        email: 'teacher@example.com',
        phone: '13800138000',
        password: 'password123',
        name: 'Test Teacher',
      };

      const mockResponse: UserInfo = {
        id: '123',
        name: 'Test Teacher',
        email: 'teacher@example.com',
        user_type: 'teacher',
      };

      vi.mocked(api.post).mockResolvedValue(mockResponse);

      // Act
      const result = await AuthService.registerTeacher(params);

      // Assert
      expect(api.post).toHaveBeenCalledWith('/api/auth/register/teacher', params);
      expect(api.post).toHaveBeenCalledTimes(1);
      expect(result).toEqual(mockResponse);
    });

    it('should throw error when registration fails', async () => {
      // Arrange
      const params: TeacherRegisterParams = {
        email: 'teacher@example.com',
        phone: '13800138000',
        password: 'password123',
        name: 'Test Teacher',
      };

      const mockError = new Error('Registration failed');
      vi.mocked(api.post).mockRejectedValue(mockError);

      // Act & Assert
      await expect(AuthService.registerTeacher(params)).rejects.toThrow('Registration failed');
      expect(api.post).toHaveBeenCalledWith('/api/auth/register/teacher', params);
    });

    it('should handle all required teacher registration fields', async () => {
      // Arrange
      const params: TeacherRegisterParams = {
        email: 'teacher@test.com',
        phone: '13912345678',
        password: 'securePass123',
        name: 'John Teacher',
      };

      const mockResponse: UserInfo = {
        id: 'teacher-123',
        name: 'John Teacher',
        email: 'teacher@test.com',
        user_type: 'teacher',
        phone: '13912345678',
      };

      vi.mocked(api.post).mockResolvedValue(mockResponse);

      // Act
      const result = await AuthService.registerTeacher(params);

      // Assert
      expect(result).toEqual(mockResponse);
      expect(result.user_type).toBe('teacher');
    });
  });

  describe('registerStudent()', () => {
    /**
     * Test: registerStudent() should call POST /api/auth/register/student
     * **Validates: Requirements 2.2**
     */
    it('should call POST /api/auth/register/student with correct parameters', async () => {
      // Arrange
      const params: StudentRegisterParams = {
        account: 'student001',
        password: 'password123',
        name: 'Test Student',
        email: 'student@example.com',
        student_id: 'S2024001',
      };

      const mockResponse: UserInfo = {
        id: '456',
        name: 'Test Student',
        email: 'student@example.com',
        user_type: 'student',
        student_id: 'S2024001',
      };

      vi.mocked(api.post).mockResolvedValue(mockResponse);

      // Act
      const result = await AuthService.registerStudent(params);

      // Assert
      expect(api.post).toHaveBeenCalledWith('/api/auth/register/student', params);
      expect(api.post).toHaveBeenCalledTimes(1);
      expect(result).toEqual(mockResponse);
    });

    it('should handle optional fields in student registration', async () => {
      // Arrange - only required fields
      const params: StudentRegisterParams = {
        account: 'student002',
        password: 'password123',
        name: 'Test Student 2',
      };

      const mockResponse: UserInfo = {
        id: '457',
        name: 'Test Student 2',
        email: '',
        user_type: 'student',
      };

      vi.mocked(api.post).mockResolvedValue(mockResponse);

      // Act
      const result = await AuthService.registerStudent(params);

      // Assert
      expect(api.post).toHaveBeenCalledWith('/api/auth/register/student', params);
      expect(result).toEqual(mockResponse);
    });

    it('should throw error when student registration fails', async () => {
      // Arrange
      const params: StudentRegisterParams = {
        account: 'student003',
        password: 'password123',
        name: 'Test Student 3',
      };

      const mockError = new Error('Student registration failed');
      vi.mocked(api.post).mockRejectedValue(mockError);

      // Act & Assert
      await expect(AuthService.registerStudent(params)).rejects.toThrow('Student registration failed');
      expect(api.post).toHaveBeenCalledWith('/api/auth/register/student', params);
    });
  });

  describe('login()', () => {
    /**
     * Test: login() should store token and user info
     * **Validates: Requirements 2.3, 2.4, 2.5**
     */
    it('should call POST /api/auth/login and store tokens and user info', async () => {
      // Arrange
      const params: LoginParams = {
        account: 'teacher@example.com',
        password: 'password123',
        user_type: 'teacher',
      };

      const mockLoginResult = {
        access_token: 'mock_access_token_12345',
        refresh_token: 'mock_refresh_token_67890',
        token_type: 'Bearer',
        expires_in: 3600,
        user: {
          id: '123',
          name: 'Test Teacher',
          email: 'teacher@example.com',
          user_type: 'teacher' as const,
        },
      };

      vi.mocked(api.post).mockResolvedValue(mockLoginResult);

      // Act
      const result = await AuthService.login(params);

      // Assert
      expect(api.post).toHaveBeenCalledWith('/api/auth/login', params);
      expect(api.post).toHaveBeenCalledTimes(1);

      // Verify tokens are stored
      expect(TokenManager.setTokens).toHaveBeenCalledWith({
        access_token: mockLoginResult.access_token,
        refresh_token: mockLoginResult.refresh_token,
        token_type: mockLoginResult.token_type,
        expires_in: mockLoginResult.expires_in,
      });
      expect(TokenManager.setTokens).toHaveBeenCalledTimes(1);

      // Verify user info is stored
      expect(TokenManager.setUserInfo).toHaveBeenCalledWith(mockLoginResult.user);
      expect(TokenManager.setUserInfo).toHaveBeenCalledTimes(1);

      // Verify result is returned
      expect(result).toEqual(mockLoginResult);
    });

    it('should handle student login', async () => {
      // Arrange
      const params: LoginParams = {
        account: 'student001',
        password: 'password123',
        user_type: 'student',
      };

      const mockLoginResult = {
        access_token: 'student_access_token',
        refresh_token: 'student_refresh_token',
        token_type: 'Bearer',
        expires_in: 7200,
        user: {
          id: '456',
          name: 'Test Student',
          email: 'student@example.com',
          user_type: 'student' as const,
          student_id: 'S2024001',
        },
      };

      vi.mocked(api.post).mockResolvedValue(mockLoginResult);

      // Act
      const result = await AuthService.login(params);

      // Assert
      expect(api.post).toHaveBeenCalledWith('/api/auth/login', params);
      expect(TokenManager.setTokens).toHaveBeenCalled();
      expect(TokenManager.setUserInfo).toHaveBeenCalledWith(mockLoginResult.user);
      expect(result.user.user_type).toBe('student');
    });

    it('should throw error when login fails', async () => {
      // Arrange
      const params: LoginParams = {
        account: 'invalid@example.com',
        password: 'wrongpassword',
        user_type: 'teacher',
      };

      const mockError = new Error('Invalid credentials');
      vi.mocked(api.post).mockRejectedValue(mockError);

      // Act & Assert
      await expect(AuthService.login(params)).rejects.toThrow('Invalid credentials');
      expect(api.post).toHaveBeenCalledWith('/api/auth/login', params);
      
      // Verify tokens are NOT stored on failure
      expect(TokenManager.setTokens).not.toHaveBeenCalled();
      expect(TokenManager.setUserInfo).not.toHaveBeenCalled();
    });

    it('should store tokens before storing user info', async () => {
      // Arrange
      const params: LoginParams = {
        account: 'test@example.com',
        password: 'password123',
        user_type: 'teacher',
      };

      const mockLoginResult = {
        access_token: 'access_token',
        refresh_token: 'refresh_token',
        token_type: 'Bearer',
        expires_in: 3600,
        user: {
          id: '123',
          name: 'Test User',
          email: 'test@example.com',
          user_type: 'teacher' as const,
        },
      };

      vi.mocked(api.post).mockResolvedValue(mockLoginResult);

      // Track call order
      const callOrder: string[] = [];
      vi.mocked(TokenManager.setTokens).mockImplementation(() => {
        callOrder.push('setTokens');
      });
      vi.mocked(TokenManager.setUserInfo).mockImplementation(() => {
        callOrder.push('setUserInfo');
      });

      // Act
      await AuthService.login(params);

      // Assert - tokens should be set before user info
      expect(callOrder).toEqual(['setTokens', 'setUserInfo']);
    });
  });

  describe('logout()', () => {
    /**
     * Test: logout() should clear all authentication data
     * **Validates: Requirements 2.9**
     */
    it('should clear all authentication data on logout', () => {
      // Act
      AuthService.logout();

      // Assert
      expect(TokenManager.clearAll).toHaveBeenCalledTimes(1);
    });

    it('should redirect to login page after logout', () => {
      // Act
      AuthService.logout();

      // Assert
      expect(window.location.href).toBe('/login');
    });

    it('should handle logout errors gracefully', () => {
      // Arrange
      vi.mocked(TokenManager.clearAll).mockImplementation(() => {
        throw new Error('Clear failed');
      });

      // Act & Assert - should not throw
      expect(() => AuthService.logout()).not.toThrow();
    });

    it('should clear tokens even if redirect fails', () => {
      // Arrange
      const originalLocation = window.location;
      delete (window as any).location;
      (window as any).location = {
        get href() {
          throw new Error('Redirect failed');
        },
        set href(value: string) {
          throw new Error('Redirect failed');
        },
      };

      // Act
      AuthService.logout();

      // Assert - clearAll should still be called
      expect(TokenManager.clearAll).toHaveBeenCalledTimes(1);

      // Cleanup
      (window as any).location = originalLocation;
    });
  });

  describe('changePassword()', () => {
    /**
     * Test: changePassword() should call correct API endpoint
     * **Validates: Requirements 2.7**
     */
    it('should call POST /api/auth/change-password with correct parameters', async () => {
      // Arrange
      const params: ChangePasswordParams = {
        old_password: 'oldPassword123',
        new_password: 'newPassword456',
      };

      vi.mocked(api.post).mockResolvedValue(undefined);

      // Act
      await AuthService.changePassword(params);

      // Assert
      expect(api.post).toHaveBeenCalledWith('/api/auth/change-password', params);
      expect(api.post).toHaveBeenCalledTimes(1);
    });

    it('should throw error when password change fails', async () => {
      // Arrange
      const params: ChangePasswordParams = {
        old_password: 'wrongOldPassword',
        new_password: 'newPassword456',
      };

      const mockError = new Error('Old password is incorrect');
      vi.mocked(api.post).mockRejectedValue(mockError);

      // Act & Assert
      await expect(AuthService.changePassword(params)).rejects.toThrow('Old password is incorrect');
      expect(api.post).toHaveBeenCalledWith('/api/auth/change-password', params);
    });

    it('should handle successful password change', async () => {
      // Arrange
      const params: ChangePasswordParams = {
        old_password: 'correctOldPassword',
        new_password: 'strongNewPassword123!',
      };

      vi.mocked(api.post).mockResolvedValue(undefined);

      // Act
      const result = await AuthService.changePassword(params);

      // Assert
      expect(result).toBeUndefined();
      expect(api.post).toHaveBeenCalledWith('/api/auth/change-password', params);
    });
  });

  describe('deleteAccount()', () => {
    /**
     * Test: deleteAccount() should call correct API endpoint and clear auth data
     * **Validates: Requirements 2.8**
     */
    it('should call POST /api/auth/delete-account with correct parameters', async () => {
      // Arrange
      const params: DeleteAccountParams = {
        password: 'password123',
      };

      const mockResponse = {
        data_retained: true,
        note: 'Account deleted successfully. Data will be retained for 30 days.',
      };

      vi.mocked(api.post).mockResolvedValue(mockResponse);

      // Act
      const result = await AuthService.deleteAccount(params);

      // Assert
      expect(api.post).toHaveBeenCalledWith('/api/auth/delete-account', params);
      expect(api.post).toHaveBeenCalledTimes(1);
      expect(result).toEqual(mockResponse);
    });

    it('should clear all authentication data after successful account deletion', async () => {
      // Arrange
      const params: DeleteAccountParams = {
        password: 'password123',
      };

      const mockResponse = {
        data_retained: false,
        note: 'Account and all data deleted permanently.',
      };

      vi.mocked(api.post).mockResolvedValue(mockResponse);

      // Act
      await AuthService.deleteAccount(params);

      // Assert
      expect(TokenManager.clearAll).toHaveBeenCalledTimes(1);
    });

    it('should throw error when account deletion fails', async () => {
      // Arrange
      const params: DeleteAccountParams = {
        password: 'wrongPassword',
      };

      const mockError = new Error('Invalid password');
      vi.mocked(api.post).mockRejectedValue(mockError);

      // Act & Assert
      await expect(AuthService.deleteAccount(params)).rejects.toThrow('Invalid password');
      expect(api.post).toHaveBeenCalledWith('/api/auth/delete-account', params);
      
      // Verify auth data is NOT cleared on failure
      expect(TokenManager.clearAll).not.toHaveBeenCalled();
    });

    it('should return data retention information', async () => {
      // Arrange
      const params: DeleteAccountParams = {
        password: 'password123',
      };

      const mockResponse = {
        data_retained: true,
        note: 'Data will be retained for 90 days for recovery purposes.',
      };

      vi.mocked(api.post).mockResolvedValue(mockResponse);

      // Act
      const result = await AuthService.deleteAccount(params);

      // Assert
      expect(result.data_retained).toBe(true);
      expect(result.note).toContain('retained');
    });

    it('should clear auth data even if API returns data_retained: false', async () => {
      // Arrange
      const params: DeleteAccountParams = {
        password: 'password123',
      };

      const mockResponse = {
        data_retained: false,
        note: 'All data permanently deleted.',
      };

      vi.mocked(api.post).mockResolvedValue(mockResponse);

      // Act
      await AuthService.deleteAccount(params);

      // Assert
      expect(TokenManager.clearAll).toHaveBeenCalledTimes(1);
    });
  });

  describe('isAuthenticated()', () => {
    /**
     * Test: isAuthenticated() should check token and user existence
     */
    it('should return true when token and user exist and token is not expired', () => {
      // Arrange
      vi.mocked(TokenManager.getAccessToken).mockReturnValue('valid_token');
      vi.mocked(TokenManager.getUserInfo).mockReturnValue({
        id: '123',
        name: 'Test User',
        email: 'test@example.com',
        user_type: 'teacher',
      });
      vi.mocked(TokenManager.isTokenExpired).mockReturnValue(false);

      // Act
      const result = AuthService.isAuthenticated();

      // Assert
      expect(result).toBe(true);
    });

    it('should return false when token does not exist', () => {
      // Arrange
      vi.mocked(TokenManager.getAccessToken).mockReturnValue(null);
      vi.mocked(TokenManager.getUserInfo).mockReturnValue({
        id: '123',
        name: 'Test User',
        email: 'test@example.com',
        user_type: 'teacher',
      });
      vi.mocked(TokenManager.isTokenExpired).mockReturnValue(false);

      // Act
      const result = AuthService.isAuthenticated();

      // Assert
      expect(result).toBe(false);
    });

    it('should return false when user info does not exist', () => {
      // Arrange
      vi.mocked(TokenManager.getAccessToken).mockReturnValue('valid_token');
      vi.mocked(TokenManager.getUserInfo).mockReturnValue(null);
      vi.mocked(TokenManager.isTokenExpired).mockReturnValue(false);

      // Act
      const result = AuthService.isAuthenticated();

      // Assert
      expect(result).toBe(false);
    });

    it('should return false when token is expired', () => {
      // Arrange
      vi.mocked(TokenManager.getAccessToken).mockReturnValue('expired_token');
      vi.mocked(TokenManager.getUserInfo).mockReturnValue({
        id: '123',
        name: 'Test User',
        email: 'test@example.com',
        user_type: 'teacher',
      });
      vi.mocked(TokenManager.isTokenExpired).mockReturnValue(true);

      // Act
      const result = AuthService.isAuthenticated();

      // Assert
      expect(result).toBe(false);
    });

    it('should return false when both token and user are missing', () => {
      // Arrange
      vi.mocked(TokenManager.getAccessToken).mockReturnValue(null);
      vi.mocked(TokenManager.getUserInfo).mockReturnValue(null);

      // Act
      const result = AuthService.isAuthenticated();

      // Assert
      expect(result).toBe(false);
    });
  });

  describe('getCurrentUser()', () => {
    /**
     * Test: getCurrentUser() should return user info from TokenManager
     */
    it('should return user info when it exists', () => {
      // Arrange
      const mockUser: UserInfo = {
        id: '123',
        name: 'Test User',
        email: 'test@example.com',
        user_type: 'teacher',
        phone: '13800138000',
      };

      vi.mocked(TokenManager.getUserInfo).mockReturnValue(mockUser);

      // Act
      const result = AuthService.getCurrentUser();

      // Assert
      expect(result).toEqual(mockUser);
      expect(TokenManager.getUserInfo).toHaveBeenCalledTimes(1);
    });

    it('should return null when user info does not exist', () => {
      // Arrange
      vi.mocked(TokenManager.getUserInfo).mockReturnValue(null);

      // Act
      const result = AuthService.getCurrentUser();

      // Assert
      expect(result).toBeNull();
      expect(TokenManager.getUserInfo).toHaveBeenCalledTimes(1);
    });

    it('should return complete user info with all fields', () => {
      // Arrange
      const mockUser: UserInfo = {
        id: '456',
        name: 'Complete User',
        email: 'complete@example.com',
        user_type: 'student',
        phone: '13912345678',
        student_id: 'S2024001',
        avatar: 'https://example.com/avatar.jpg',
        created_at: '2024-01-01T00:00:00Z',
      };

      vi.mocked(TokenManager.getUserInfo).mockReturnValue(mockUser);

      // Act
      const result = AuthService.getCurrentUser();

      // Assert
      expect(result).toEqual(mockUser);
      expect(result?.student_id).toBe('S2024001');
      expect(result?.avatar).toBe('https://example.com/avatar.jpg');
    });
  });

  describe('refreshToken()', () => {
    /**
     * Test: refreshToken() should delegate to TokenManager
     */
    it('should call TokenManager.refreshToken()', async () => {
      // Arrange
      const mockTokenData: TokenData = {
        access_token: 'new_access_token',
        refresh_token: 'new_refresh_token',
        token_type: 'Bearer',
        expires_in: 3600,
      };

      vi.mocked(TokenManager.refreshToken).mockResolvedValue(mockTokenData);

      // Act
      const result = await AuthService.refreshToken();

      // Assert
      expect(TokenManager.refreshToken).toHaveBeenCalledTimes(1);
      expect(result).toEqual(mockTokenData);
    });

    it('should throw error when token refresh fails', async () => {
      // Arrange
      const mockError = new Error('Refresh token expired');
      vi.mocked(TokenManager.refreshToken).mockRejectedValue(mockError);

      // Act & Assert
      await expect(AuthService.refreshToken()).rejects.toThrow('Refresh token expired');
      expect(TokenManager.refreshToken).toHaveBeenCalledTimes(1);
    });
  });

  describe('Integration scenarios', () => {
    it('should handle complete login-logout flow', async () => {
      // Arrange - Login
      const loginParams: LoginParams = {
        account: 'user@example.com',
        password: 'password123',
        user_type: 'teacher',
      };

      const mockLoginResult = {
        access_token: 'access_token',
        refresh_token: 'refresh_token',
        token_type: 'Bearer',
        expires_in: 3600,
        user: {
          id: '123',
          name: 'Test User',
          email: 'user@example.com',
          user_type: 'teacher' as const,
        },
      };

      vi.mocked(api.post).mockResolvedValue(mockLoginResult);

      // Act - Login
      await AuthService.login(loginParams);

      // Assert - Login
      expect(TokenManager.setTokens).toHaveBeenCalled();
      expect(TokenManager.setUserInfo).toHaveBeenCalled();

      // Act - Logout
      AuthService.logout();

      // Assert - Logout
      expect(TokenManager.clearAll).toHaveBeenCalled();
    });

    it('should handle registration followed by login', async () => {
      // Arrange - Registration
      const registerParams: TeacherRegisterParams = {
        email: 'newteacher@example.com',
        phone: '13800138000',
        password: 'password123',
        name: 'New Teacher',
      };

      const mockRegisterResponse: UserInfo = {
        id: '789',
        name: 'New Teacher',
        email: 'newteacher@example.com',
        user_type: 'teacher',
      };

      vi.mocked(api.post).mockResolvedValueOnce(mockRegisterResponse);

      // Act - Registration
      const registerResult = await AuthService.registerTeacher(registerParams);

      // Assert - Registration
      expect(registerResult).toEqual(mockRegisterResponse);

      // Arrange - Login
      const loginParams: LoginParams = {
        account: 'newteacher@example.com',
        password: 'password123',
        user_type: 'teacher',
      };

      const mockLoginResult = {
        access_token: 'access_token',
        refresh_token: 'refresh_token',
        token_type: 'Bearer',
        expires_in: 3600,
        user: mockRegisterResponse,
      };

      vi.mocked(api.post).mockResolvedValueOnce(mockLoginResult);

      // Act - Login
      await AuthService.login(loginParams);

      // Assert - Login
      expect(TokenManager.setTokens).toHaveBeenCalled();
      expect(TokenManager.setUserInfo).toHaveBeenCalledWith(mockRegisterResponse);
    });
  });
});
