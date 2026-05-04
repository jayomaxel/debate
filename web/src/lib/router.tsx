import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';

export interface AppLocation {
  pathname: string;
  search: string;
  hash: string;
}

export interface NavigateOptions {
  replace?: boolean;
}

export interface RouteMatch {
  params: Record<string, string>;
}

export interface NavigationAttempt {
  to: string;
  type: 'navigate' | 'back' | 'popstate';
}

interface RegisteredNavigationBlocker {
  id: symbol;
  message: string;
  shouldBlock: () => boolean;
  onBlock?: (attempt: NavigationAttempt) => void;
}

interface RouterContextValue {
  location: AppLocation;
  navigate: (to: string, options?: NavigateOptions) => void;
  back: (fallbackPath?: string) => void;
  registerBlocker: (
    blocker: RegisteredNavigationBlocker
  ) => () => void;
  allowNextNavigation: () => void;
}

interface UseNavigationBlockerOptions {
  when: boolean;
  message: string;
  onBlock?: (attempt: NavigationAttempt) => void;
}

const RouterContext = createContext<RouterContextValue | null>(null);

const normalizePathname = (pathname: string) => {
  if (!pathname) {
    return '/';
  }

  const withLeadingSlash = pathname.startsWith('/') ? pathname : `/${pathname}`;
  const trimmed = withLeadingSlash.replace(/\/+$/, '');
  return trimmed || '/';
};

const getLocationSnapshot = (): AppLocation => {
  if (typeof window === 'undefined') {
    return {
      pathname: '/',
      search: '',
      hash: '',
    };
  }

  return {
    pathname: normalizePathname(window.location.pathname),
    search: window.location.search,
    hash: window.location.hash,
  };
};

const toUrl = (to: string) => {
  if (typeof window === 'undefined') {
    return new URL(`https://example.com${normalizePathname(to)}`);
  }

  return new URL(to, window.location.origin);
};

const toLocationPath = (location: AppLocation) =>
  `${location.pathname}${location.search}${location.hash}`;

const splitPath = (path: string) =>
  normalizePathname(path)
    .split('/')
    .filter(Boolean);

export const matchPath = (
  pattern: string,
  pathname: string
): RouteMatch | null => {
  const patternParts = splitPath(pattern);
  const pathParts = splitPath(pathname);

  if (patternParts.length !== pathParts.length) {
    return null;
  }

  const params: Record<string, string> = {};

  for (let index = 0; index < patternParts.length; index += 1) {
    const patternPart = patternParts[index];
    const pathPart = pathParts[index];

    if (patternPart.startsWith(':')) {
      params[patternPart.slice(1)] = decodeURIComponent(pathPart);
      continue;
    }

    if (patternPart !== pathPart) {
      return null;
    }
  }

  return { params };
};

interface RouterProviderProps {
  children: React.ReactNode;
}

export function RouterProvider({ children }: RouterProviderProps) {
  const [location, setLocation] = useState<AppLocation>(() => getLocationSnapshot());
  const locationRef = useRef(location);
  const blockersRef = useRef<Map<symbol, RegisteredNavigationBlocker>>(new Map());
  const bypassCountRef = useRef(0);

  useEffect(() => {
    locationRef.current = location;
  }, [location]);

  const getBlockedMessage = useCallback((attempt: NavigationAttempt) => {
    if (bypassCountRef.current > 0) {
      bypassCountRef.current -= 1;
      return null;
    }

    for (const blocker of blockersRef.current.values()) {
      if (!blocker.shouldBlock()) {
        continue;
      }

      blocker.onBlock?.(attempt);
      return blocker.message;
    }

    return null;
  }, []);

  useEffect(() => {
    const handlePopState = () => {
      const nextLocation = getLocationSnapshot();
      const nextPath = toLocationPath(nextLocation);
      const blockedMessage = getBlockedMessage({
        to: nextPath,
        type: 'popstate',
      });

      if (blockedMessage) {
        const currentLocation = locationRef.current;
        window.history.pushState({}, '', toLocationPath(currentLocation));
        setLocation(currentLocation);
        return;
      }

      locationRef.current = nextLocation;
      setLocation(nextLocation);
    };

    const handleLocationChange = () => {
      const nextLocation = getLocationSnapshot();
      locationRef.current = nextLocation;
      setLocation(nextLocation);
    };

    window.addEventListener('popstate', handlePopState);
    window.addEventListener('app:navigation', handleLocationChange);

    return () => {
      window.removeEventListener('popstate', handlePopState);
      window.removeEventListener('app:navigation', handleLocationChange);
    };
  }, [getBlockedMessage]);

  const navigate = useCallback(
    (to: string, options?: NavigateOptions) => {
      if (typeof window === 'undefined') {
        return;
      }

      const url = toUrl(to);
      const nextLocation = {
        pathname: normalizePathname(url.pathname),
        search: url.search,
        hash: url.hash,
      };
      const nextPath = toLocationPath(nextLocation);
      const blockedMessage = getBlockedMessage({
        to: nextPath,
        type: 'navigate',
      });

      if (blockedMessage) {
        return;
      }

      if (options?.replace) {
        window.history.replaceState({}, '', nextPath);
      } else {
        window.history.pushState({}, '', nextPath);
      }

      locationRef.current = nextLocation;
      setLocation(nextLocation);
      window.dispatchEvent(new Event('app:navigation'));
    },
    [getBlockedMessage]
  );

  const back = useCallback(
    (fallbackPath = '/') => {
      if (typeof window === 'undefined') {
        return;
      }

      const blockedMessage = getBlockedMessage({
        to: fallbackPath,
        type: 'back',
      });

      if (blockedMessage) {
        return;
      }

      if (window.history.length > 1) {
        window.history.back();
        return;
      }

      navigate(fallbackPath, { replace: true });
    },
    [getBlockedMessage, navigate]
  );

  const registerBlocker = useCallback(
    (blocker: RegisteredNavigationBlocker) => {
      blockersRef.current.set(blocker.id, blocker);

      return () => {
        blockersRef.current.delete(blocker.id);
      };
    },
    []
  );

  const allowNextNavigation = useCallback(() => {
    bypassCountRef.current += 1;
  }, []);

  const value = useMemo<RouterContextValue>(
    () => ({
      location,
      navigate,
      back,
      registerBlocker,
      allowNextNavigation,
    }),
    [allowNextNavigation, back, location, navigate, registerBlocker]
  );

  return <RouterContext.Provider value={value}>{children}</RouterContext.Provider>;
}

export function useAppRouter() {
  const context = useContext(RouterContext);

  if (!context) {
    throw new Error('useAppRouter must be used within a RouterProvider');
  }

  return context;
}

export function useNavigationBlocker({
  when,
  message,
  onBlock,
}: UseNavigationBlockerOptions) {
  const { registerBlocker, allowNextNavigation } = useAppRouter();
  const blockerIdRef = useRef<symbol | null>(null);

  if (blockerIdRef.current === null) {
    blockerIdRef.current = Symbol('app-router-blocker');
  }

  useEffect(() => {
    return registerBlocker({
      id: blockerIdRef.current as symbol,
      message,
      shouldBlock: () => when,
      onBlock,
    });
  }, [message, onBlock, registerBlocker, when]);

  return {
    allowNextNavigation,
  };
}

export const routerUtils = {
  normalizePathname,
};
