import React from 'react';
import { useAuth } from '@/store/auth.context';
import { useAppRouter } from '@/lib/router';
import { cn } from '@/lib/utils';
import {
  getStudentAnalyticsPath,
  getStudentSettingsPath,
} from '@/lib/route-utils';
import UserMenu from '@/components/user-menu';
import brandLogo from '../../pic/c99ec0bb69f6f215f2fe76bc7536d56a.jpg';

interface StudentLayoutProps {
  children: React.ReactNode;
}

const navItems = [
  { label: '首页', href: '/student' },
  { label: '比赛', href: '/student/competition' },
  { label: '备赛', href: '/student/preparation' },
  { label: '成长', href: getStudentAnalyticsPath('history') },
];

const isItemActive = (pathname: string, href: string) => {
  if (href === '/student') return pathname === '/student';
  if (
    href === '/student/competition' &&
    (pathname === '/student/waiting' || pathname.startsWith('/student/lobby'))
  ) {
    return true;
  }
  return pathname === href || pathname.startsWith(`${href}/`);
};

export default function StudentLayout({ children }: StudentLayoutProps) {
  const { user, logout } = useAuth();
  const { location, navigate } = useAppRouter();
  const pathname = location.pathname;

  return (
    <div className="student-theme">
      <div className="student-shell">
        <header className="sticky top-0 z-40">
          <div className="w-full">
            <div className="student-header-frame flex items-center justify-between gap-4 rounded-none px-5 py-3 sm:px-6">
              <button
                type="button"
                onClick={() => navigate('/student')}
                className="min-w-0 flex items-center gap-3 text-left"
              >
                <div className="student-icon-bubble overflow-hidden bg-white p-0 shadow-[0_14px_30px_rgba(15,23,42,0.18)]">
                  <img src={brandLogo} alt="" className="h-full w-full object-cover" />
                </div>
                <div className="min-w-0">
                  <div className="truncate text-lg font-semibold tracking-[-0.03em] text-slate-900">
                    碳硅之辩
                  </div>
                  <div className="truncate text-xs uppercase tracking-[0.22em] text-slate-500">
                    Debate Workspace
                  </div>
                </div>
              </button>

              <nav className="hidden flex-1 items-center justify-center gap-2 md:flex">
                {navItems.map((item) => (
                  <button
                    key={item.href}
                    type="button"
                    className={cn(
                      'student-nav-pill',
                      isItemActive(pathname, item.href) && 'student-nav-pill-active'
                    )}
                    onClick={() => navigate(item.href)}
                  >
                    {item.label}
                  </button>
                ))}
              </nav>

              <div className="flex items-center gap-2">
                {user ? (
                  <UserMenu
                    user={user}
                    homeLabel="返回首页"
                    onNavigateHome={() => navigate('/student')}
                    onNavigateProfile={() => navigate(getStudentSettingsPath('info'))}
                    onNavigateSecurity={() =>
                      navigate(getStudentSettingsPath('password'))
                    }
                    onLogout={logout}
                  />
                ) : null}
              </div>
            </div>
          </div>
        </header>

        <div className="student-container mt-3 md:hidden">
          <nav className="student-responsive-nav">
            {navItems.map((item) => (
              <button
                key={item.href}
                type="button"
                className={cn(
                  'student-nav-pill shrink-0',
                  isItemActive(pathname, item.href) && 'student-nav-pill-active'
                )}
                onClick={() => navigate(item.href)}
              >
                {item.label}
              </button>
            ))}
          </nav>
        </div>

        <main>{children}</main>
      </div>
    </div>
  );
}

