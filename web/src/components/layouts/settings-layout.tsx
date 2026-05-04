import React from 'react';
import { ArrowLeft, Settings } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface SettingsLayoutProps {
  children: React.ReactNode;
  onBack: () => void;
}

export default function SettingsLayout({
  children,
  onBack,
}: SettingsLayoutProps) {
  return (
    <div className="student-theme">
      <div className="student-shell">
        <header>
          <div className="w-full">
            <div className="student-header-frame flex items-center justify-between rounded-none px-5 py-4 sm:px-6">
              <div className="flex items-center gap-3">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={onBack}
                  className="student-light-button h-auto px-4 py-2"
                >
                  <ArrowLeft className="mr-2 h-4 w-4" />
                  返回
                </Button>
                <div className="flex items-center gap-3 text-slate-900">
                  <div className="student-icon-bubble h-11 w-11 bg-[#151515] text-white">
                    <Settings className="h-5 w-5" />
                  </div>
                  <div>
                    <div className="text-lg font-semibold tracking-[-0.03em]">
                      设置中心
                    </div>
                    <div className="text-xs uppercase tracking-[0.22em] text-slate-500">
                      Profile & Preferences
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </header>

        <main className="student-container pb-10 pt-2">{children}</main>
      </div>
    </div>
  );
}
