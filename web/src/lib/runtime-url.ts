type ImportMetaWithRuntimeEnv = ImportMeta & {
  env?: {
    DEV?: boolean;
    VITE_API_BASE_URL?: string;
    VITE_DEV_API_PROXY_TARGET?: string;
    VITE_DEV_API_ORIGIN?: string;
    VITE_WS_BASE_URL?: string;
  };
};

const stripTrailingSlashes = (value?: string) => (value || '').replace(/\/+$/, '');

const isPrivateLanHostname = (hostname: string) =>
  hostname.startsWith('10.') ||
  hostname.startsWith('192.168.') ||
  /^172\.(1[6-9]|2\d|3[0-1])\./.test(hostname);

const isLoopbackHostname = (hostname: string) =>
  hostname === 'localhost' ||
  hostname === '127.0.0.1' ||
  hostname === '0.0.0.0' ||
  hostname === '::1';

export const shouldUseSameOriginBackend = () => {
  if (typeof window === 'undefined') {
    return false;
  }

  const hostname = window.location.hostname.toLowerCase();
  return (
    isLoopbackHostname(hostname) ||
    hostname.endsWith('.local') ||
    isPrivateLanHostname(hostname)
  );
};

export const getApiBaseUrl = () => {
  if (shouldUseSameOriginBackend()) {
    return '';
  }

  return stripTrailingSlashes(
    (import.meta as ImportMetaWithRuntimeEnv).env?.VITE_API_BASE_URL
  );
};

export const getApiOriginBaseUrl = () =>
  getApiBaseUrl()
    .replace(/\/api\/v\d+$/i, '')
    .replace(/\/api$/i, '');

export const getWebSocketBaseUrl = () => {
  const env = (import.meta as ImportMetaWithRuntimeEnv).env;
  const hostname = typeof window !== 'undefined' ? window.location.hostname.toLowerCase() : '';
  if (env?.DEV && isLoopbackHostname(hostname)) {
    const devApiOrigin = stripTrailingSlashes(
      env.VITE_DEV_API_ORIGIN ||
        env.VITE_DEV_API_PROXY_TARGET ||
        'http://localhost:7861'
    );
    return devApiOrigin
      .replace(/^https:/i, 'wss:')
      .replace(/^http:/i, 'ws:')
      .replace(/\/api$/i, '');
  }

  if (shouldUseSameOriginBackend() && typeof window !== 'undefined') {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${window.location.host}`;
  }

  const envWsBase = stripTrailingSlashes(env?.VITE_WS_BASE_URL);
  if (envWsBase) {
    return envWsBase.replace(/\/ws$/i, '');
  }

  const envApiBase = getApiBaseUrl();
  if (envApiBase) {
    return envApiBase
      .replace(/^https:/i, 'wss:')
      .replace(/^http:/i, 'ws:')
      .replace(/\/api$/i, '');
  }

  if (typeof window === 'undefined') {
    return '';
  }

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}`;
};
