import React from 'react';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/store/auth.context';
import { useAppRouter } from '@/lib/router';
import { cn } from '@/lib/utils';
import {
  getDefaultHomePath,
  getPublicSectionPath,
  getStudentSettingsPath,
  type PublicSection,
} from '@/lib/route-utils';
import UserMenu from '@/components/user-menu';
import brandLogo from '../../../../pic/c99ec0bb69f6f215f2fe76bc7536d56a.jpg';

interface PublicLayoutProps {
  activeSection?: PublicSection;
  children: React.ReactNode;
}

const navItems: Array<{ key: PublicSection; label: string }> = [
  { key: 'home', label: '首页' },
  { key: 'competition', label: '比赛' },
  { key: 'preparation', label: '备赛' },
  { key: 'growth', label: '成长' },
];

export default function PublicLayout({
  activeSection = 'home',
  children,
}: PublicLayoutProps) {
  const { isAuthenticated, user, logout } = useAuth();
  const { navigate } = useAppRouter();
  const isStudent = user?.user_type === 'student';

  return (
    <div className="student-theme">
      <div className="student-shell">
        <header className="sticky top-0 z-40">
          <div className="w-full">
            <div className="student-header-frame relative flex items-center justify-between gap-4 rounded-none px-5 py-3 sm:px-6">
              <button
                type="button"
                onClick={() => navigate('/')}
                className="min-w-0 flex items-center gap-3 text-left"
              >
                <div className="student-icon-bubble overflow-hidden bg-white p-0 shadow-[0_14px_30px_rgba(15,23,42,0.18)]">
                  <img src={brandLogo} alt="" className="h-full w-full object-cover" />
                </div>
                <div className="min-w-0">
                  <div className="truncate text-lg font-semibold tracking-[-0.03em] text-slate-900">
                    碳硅之辩
                  </div>
                </div>
              </button>

              <nav className="absolute left-1/2 top-1/2 hidden -translate-x-1/2 -translate-y-1/2 items-center justify-center gap-2 md:flex">
                {navItems.map((item) => (
                  <button
                    key={item.key}
                    type="button"
                    className={cn(
                      'student-nav-pill',
                      activeSection === item.key && 'student-nav-pill-active'
                    )}
                    onClick={() => navigate(getPublicSectionPath(item.key))}
                  >
                    {item.label}
                  </button>
                ))}
              </nav>

              <div className="ml-auto flex items-center gap-2">
                {isAuthenticated && user ? (
                  <UserMenu
                    user={user}
                    onNavigateHome={() =>
                      navigate(getDefaultHomePath(user.user_type))
                    }
                    onNavigateProfile={
                      isStudent
                        ? () => navigate(getStudentSettingsPath('info'))
                        : undefined
                    }
                    onNavigateSecurity={
                      isStudent
                        ? () => navigate(getStudentSettingsPath('password'))
                        : undefined
                    }
                    onLogout={logout}
                  />
                ) : (
                  <Button
                    onClick={() => navigate('/login')}
                    className="student-dark-button h-auto"
                  >
                    登录
                  </Button>
                )}
              </div>
            </div>
          </div>
        </header>

        <div className="student-container mt-3 md:hidden">
          <nav className="student-responsive-nav">
            {navItems.map((item) => (
              <button
                key={item.key}
                type="button"
                className={cn(
                  'student-nav-pill shrink-0',
                  activeSection === item.key && 'student-nav-pill-active'
                )}
                onClick={() => navigate(getPublicSectionPath(item.key))}
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

