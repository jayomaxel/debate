import axios from 'axios';

type ErrorPayload = {
  detail?: unknown;
  message?: unknown;
  error?: unknown;
};

const stringifyPayload = (value: unknown): string | null => {
  if (!value) {
    return null;
  }

  if (typeof value === 'string') {
    return value;
  }

  if (Array.isArray(value)) {
    return value
      .map((item) => stringifyPayload(item))
      .filter(Boolean)
      .join('; ');
  }

  if (typeof value === 'object') {
    const payload = value as ErrorPayload;
    return (
      stringifyPayload(payload.detail) ||
      stringifyPayload(payload.message) ||
      stringifyPayload(payload.error) ||
      JSON.stringify(value)
    );
  }

  return String(value);
};

export function formatErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as ErrorPayload | undefined;
    return (
      stringifyPayload(data?.detail) ||
      stringifyPayload(data?.message) ||
      error.message ||
      '请求失败'
    );
  }

  if (error instanceof Error) {
    return error.message;
  }

  return stringifyPayload(error) || '操作失败，请稍后重试';
}
