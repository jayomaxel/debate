/**
 * Error Handler
 * 统一的错误处理工具
 */

import { AxiosError } from 'axios';
import type { ApiError } from './api';

export enum ErrorType {
  NETWORK_ERROR = 'NETWORK_ERROR',
  AUTHENTICATION_ERROR = 'AUTHENTICATION_ERROR',
  AUTHORIZATION_ERROR = 'AUTHORIZATION_ERROR',
  NOT_FOUND_ERROR = 'NOT_FOUND_ERROR',
  VALIDATION_ERROR = 'VALIDATION_ERROR',
  SERVER_ERROR = 'SERVER_ERROR',
  TIMEOUT_ERROR = 'TIMEOUT_ERROR',
  UNKNOWN_ERROR = 'UNKNOWN_ERROR',
}

export interface AppError {
  type: ErrorType;
  code: number;
  message: string;
  detail?: string;
  originalError?: any;
}

/**
 * 根据HTTP状态码分类错误
 */
export function classifyError(error: any): ErrorType {
  // 处理ApiError
  if (error && typeof error === 'object' && 'code' in error) {
    const code = error.code;

    if (code === 0) {
      return ErrorType.NETWORK_ERROR;
    }

    if (code === 401) {
      return ErrorType.AUTHENTICATION_ERROR;
    }

    if (code === 403) {
      return ErrorType.AUTHORIZATION_ERROR;
    }

    if (code === 404) {
      return ErrorType.NOT_FOUND_ERROR;
    }

    if (code === 400 || code === 422) {
      return ErrorType.VALIDATION_ERROR;
    }

    if (code === 408 || code === 504) {
      return ErrorType.TIMEOUT_ERROR;
    }

    if (code >= 500 && code < 600) {
      return ErrorType.SERVER_ERROR;
    }
  }

  // 处理AxiosError
  if (error && typeof error === 'object' && 'isAxiosError' in error) {
    const axiosError = error as AxiosError;

    if (!axiosError.response) {
      return ErrorType.NETWORK_ERROR;
    }

    const status = axiosError.response.status;

    if (status === 401) {
      return ErrorType.AUTHENTICATION_ERROR;
    }

    if (status === 403) {
      return ErrorType.AUTHORIZATION_ERROR;
    }

    if (status === 404) {
      return ErrorType.NOT_FOUND_ERROR;
    }

    if (status === 400 || status === 422) {
      return ErrorType.VALIDATION_ERROR;
    }

    if (status === 408 || status === 504) {
      return ErrorType.TIMEOUT_ERROR;
    }

    if (status >= 500 && status < 600) {
      return ErrorType.SERVER_ERROR;
    }
  }

  return ErrorType.UNKNOWN_ERROR;
}

/**
 * 生成用户友好的错误消息
 */
export function formatErrorMessage(error: any): string {
  const errorType = classifyError(error);

  // 如果错误对象已经有message，优先使用
  if (error && typeof error === 'object' && 'message' in error && error.message) {
    if (typeof error.message === 'string') {
      return error.message;
    }
    // 如果message是对象或数组（如422验证错误的detail），尝试转换
    if (typeof error.message === 'object') {
      try {
        if (Array.isArray(error.message)) {
          // 处理 FastAPI/Pydantic 的验证错误数组
          return error.message
            .map((m: any) => {
              if (typeof m === 'string') return m;
              if (typeof m === 'object' && m.msg) return m.msg;
              return JSON.stringify(m);
            })
            .join('; ');
        }
        return JSON.stringify(error.message);
      } catch (e) {
        return '输入数据格式错误';
      }
    }
    return String(error.message);
  }

  // 根据错误类型返回默认消息
  const defaultMessages: Record<ErrorType, string> = {
    [ErrorType.NETWORK_ERROR]: '网络连接失败，请检查网络设置',
    [ErrorType.AUTHENTICATION_ERROR]: '身份验证失败，请重新登录',
    [ErrorType.AUTHORIZATION_ERROR]: '您没有权限执行此操作',
    [ErrorType.NOT_FOUND_ERROR]: '请求的资源不存在',
    [ErrorType.VALIDATION_ERROR]: '输入数据验证失败，请检查输入',
    [ErrorType.SERVER_ERROR]: '服务器错误，请稍后重试',
    [ErrorType.TIMEOUT_ERROR]: '请求超时，请稍后重试',
    [ErrorType.UNKNOWN_ERROR]: '发生未知错误，请稍后重试',
  };

  return defaultMessages[errorType];
}

/**
 * 创建AppError对象
 */
export function createAppError(error: any): AppError {
  const errorType = classifyError(error);
  const message = formatErrorMessage(error);

  let code = -1;
  let detail: string | undefined;

  if (error && typeof error === 'object') {
    if ('code' in error) {
      code = error.code;
    }
    if ('detail' in error) {
      detail = error.detail;
    }
  }

  return {
    type: errorType,
    code,
    message,
    detail,
    originalError: error,
  };
}

/**
 * 判断错误是否可重试
 */
export function isRetryableError(error: any): boolean {
  const errorType = classifyError(error);

  return (
    errorType === ErrorType.NETWORK_ERROR ||
    errorType === ErrorType.TIMEOUT_ERROR ||
    errorType === ErrorType.SERVER_ERROR
  );
}

/**
 * 判断错误是否需要重新登录
 */
export function requiresReauth(error: any): boolean {
  const errorType = classifyError(error);
  return errorType === ErrorType.AUTHENTICATION_ERROR;
}

/**
 * 获取错误的用户提示
 */
export function getErrorHint(error: any): string | null {
  const errorType = classifyError(error);

  const hints: Partial<Record<ErrorType, string>> = {
    [ErrorType.NETWORK_ERROR]: '请检查您的网络连接是否正常',
    [ErrorType.AUTHENTICATION_ERROR]: '请点击重新登录按钮',
    [ErrorType.AUTHORIZATION_ERROR]: '如需访问此功能，请联系管理员',
    [ErrorType.VALIDATION_ERROR]: '请检查表单中的输入是否正确',
    [ErrorType.TIMEOUT_ERROR]: '请稍后再试或检查网络连接',
  };

  return hints[errorType] || null;
}

/**
 * 日志记录错误（开发环境）
 */
export function logError(error: any, context?: string): void {
  if ((import.meta as any).env?.DEV) {
    const appError = createAppError(error);
    console.group(`[Error Handler] ${context || 'Error'}`);
    console.error('Type:', appError.type);
    console.error('Code:', appError.code);
    console.error('Message:', appError.message);
    if (appError.detail) {
      console.error('Detail:', appError.detail);
    }
    console.error('Original Error:', appError.originalError);
    console.groupEnd();
  }
}

export default {
  classifyError,
  formatErrorMessage,
  createAppError,
  isRetryableError,
  requiresReauth,
  getErrorHint,
  logError,
};
