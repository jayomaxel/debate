import React from 'react';
import { BrainCircuit } from 'lucide-react';
import { useAuth } from '@/store/auth.context';
import { useAppRouter } from '@/lib/router';
import UserMenu from '@/components/user-menu';

interface AdminLayoutProps {
  children: React.ReactNode;
}

export default function AdminLayout({ children }: AdminLayoutProps) {
  const { user, logout } = useAuth();
  const { navigate } = useAppRouter();

  return (
    <div className="student-theme">
      <div className="student-shell">
        <header className="sticky top-0 z-40">
          <div className="w-full">
            <div className="student-header-frame flex items-center justify-between gap-4 rounded-none px-5 py-3 sm:px-6">
              <button
                type="button"
                onClick={() => navigate('/admin')}
                className="min-w-0 flex items-center gap-3 text-left"
              >
                <div className="student-icon-bubble bg-[#151515] text-white shadow-[0_14px_30px_rgba(15,23,42,0.18)]">
                  <BrainCircuit className="h-6 w-6" />
                </div>
                <div className="min-w-0">
                  <div className="truncate text-lg font-semibold tracking-[-0.03em] text-slate-900">
                    碳硅之辩
                  </div>
                  <div className="truncate text-xs uppercase tracking-[0.22em] text-slate-500">
                    Admin Workspace
                  </div>
                </div>
              </button>

              <div className="flex items-center gap-2">
                {user ? <UserMenu user={user} onLogout={logout} /> : null}
              </div>
            </div>
          </div>
        </header>
        <main>{children}</main>
      </div>
    </div>
  );
}
