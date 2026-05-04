import React, { useEffect } from 'react';
import { Loader2 } from 'lucide-react';
import { useAuth } from '@/store/auth.context';
import { useAppRouter } from '@/lib/router';
import { getDefaultHomePath } from '@/lib/route-utils';
import { useStudentAssessment } from '@/hooks/use-student-assessment';
import type { UserInfo } from '@/lib/token-manager';

interface GuardProps {
  children: React.ReactNode;
}

interface RequireRoleProps extends GuardProps {
  role: UserInfo['user_type'] | UserInfo['user_type'][];
}

interface RequireStudentAssessmentProps extends GuardProps {
  redirectTo?: string;
}

const FullscreenLoader = () => (
  <div className="flex min-h-screen items-center justify-center bg-slate-50">
    <div className="text-center text-slate-600">
      <Loader2 className="mx-auto mb-4 h-10 w-10 animate-spin text-slate-700" />
      <p>正在加载页面...</p>
    </div>
  </div>
);

export function RequireGuest({ children }: GuardProps) {
  const { isAuthenticated, loading, user } = useAuth();
  const { navigate } = useAppRouter();

  useEffect(() => {
    if (!loading && isAuthenticated) {
      navigate(getDefaultHomePath(user?.user_type), { replace: true });
    }
  }, [isAuthenticated, loading, navigate, user?.user_type]);

  if (loading || isAuthenticated) {
    return <FullscreenLoader />;
  }

  return <>{children}</>;
}

export function RequireAuth({ children }: GuardProps) {
  const { isAuthenticated, loading } = useAuth();
  const { navigate } = useAppRouter();

  useEffect(() => {
    if (!loading && !isAuthenticated) {
      navigate('/login', { replace: true });
    }
  }, [isAuthenticated, loading, navigate]);

  if (loading || !isAuthenticated) {
    return <FullscreenLoader />;
  }

  return <>{children}</>;
}

export function RequireRole({ children, role }: RequireRoleProps) {
  const { user } = useAuth();
  const { navigate } = useAppRouter();
  const roles = Array.isArray(role) ? role : [role];
  const currentRole = user?.user_type;
  const allowed = !!currentRole && roles.includes(currentRole);

  useEffect(() => {
    if (!allowed) {
      navigate(getDefaultHomePath(currentRole), { replace: true });
    }
  }, [allowed, currentRole, navigate]);

  if (!allowed) {
    return <FullscreenLoader />;
  }

  return <>{children}</>;
}

export function RequireStudentAssessment({
  children,
  redirectTo = '/student/settings?tab=ability',
}: RequireStudentAssessmentProps) {
  const { needsAssessment, loading } = useStudentAssessment(true);
  const { navigate } = useAppRouter();

  useEffect(() => {
    if (!loading && needsAssessment) {
      navigate(redirectTo, { replace: true });
    }
  }, [loading, navigate, needsAssessment, redirectTo]);

  if (loading || needsAssessment) {
    return <FullscreenLoader />;
  }

  return <>{children}</>;
}

export function useProtectedAction() {
  const { isAuthenticated, loading } = useAuth();
  const { navigate } = useAppRouter();

  const ensureAuthenticated = () => {
    if (loading) {
      return false;
    }

    if (!isAuthenticated) {
      navigate('/login');
      return false;
    }

    return true;
  };

  const runProtectedAction = async <T,>(
    action: () => Promise<T> | T
  ): Promise<T | undefined> => {
    if (!ensureAuthenticated()) {
      return undefined;
    }

    return await action();
  };

  return {
    ensureAuthenticated,
    runProtectedAction,
  };
}
