import React from 'react';
import { ChevronDown, Lock, LogOut, User } from 'lucide-react';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import type { UserInfo } from '@/lib/token-manager';

interface UserMenuProps {
  user: UserInfo;
  homeLabel?: string;
  onNavigateHome?: () => void;
  onNavigateProfile?: () => void;
  onNavigateSecurity?: () => void;
  onLogout: () => void;
}

const getRoleLabel = (userType?: string) => {
  if (userType === 'teacher') return '教师';
  if (userType === 'administrator') return '管理员';
  return '学生';
};

const getUserInitial = (name?: string | null) =>
  String(name || 'U').trim().slice(0, 1).toUpperCase();

export default function UserMenu({
  user,
  homeLabel = '返回首页',
  onNavigateHome,
  onNavigateProfile,
  onNavigateSecurity,
  onLogout,
}: UserMenuProps) {
  void homeLabel;
  void onNavigateHome;
  const avatarSrc = user.avatar_url || user.avatar || undefined;
  const roleLabel = getRoleLabel(user.user_type);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="flex items-center gap-3 rounded-[18px] border border-black/10 bg-white/85 px-2.5 py-2 text-left shadow-[0_10px_24px_rgba(15,23,42,0.06)] transition-colors duration-150 hover:border-black/15 hover:bg-[#faf7f2] focus-visible:ring-black/15 focus-visible:ring-offset-0"
        >
          <Avatar className="h-9 w-9 border border-black/10">
            <AvatarImage src={avatarSrc} alt={user.name} />
            <AvatarFallback className="bg-[#f3e7d8] text-sm font-semibold text-[#7a4c2a]">
              {getUserInitial(user.name)}
            </AvatarFallback>
          </Avatar>
          <div className="hidden min-w-0 sm:block">
            <div className="max-w-[120px] truncate text-sm font-medium text-slate-900">
              {user.name}
            </div>
            <div className="text-xs text-slate-500">{roleLabel}</div>
          </div>
          <ChevronDown className="h-4 w-4 text-slate-400" />
        </button>
      </DropdownMenuTrigger>

      <DropdownMenuContent
        align="end"
        sideOffset={10}
        className="w-56 rounded-[20px] border border-black/10 bg-white/95 p-2 shadow-[0_18px_40px_rgba(15,23,42,0.12)] backdrop-blur"
      >
        <DropdownMenuLabel className="px-3 py-2">
          <div className="text-sm font-semibold text-slate-900">{user.name}</div>
          <div className="text-xs font-normal text-slate-500">{roleLabel}</div>
        </DropdownMenuLabel>

        {onNavigateProfile ? (
          <DropdownMenuItem
            onSelect={onNavigateProfile}
            className="rounded-[14px] px-3 py-2 focus:bg-[#f6efe6]"
          >
            <User className="mr-2 h-4 w-4" />
            个人资料
          </DropdownMenuItem>
        ) : null}

        {onNavigateSecurity ? (
          <DropdownMenuItem
            onSelect={onNavigateSecurity}
            className="rounded-[14px] px-3 py-2 focus:bg-[#f6efe6]"
          >
            <Lock className="mr-2 h-4 w-4" />
            修改密码
          </DropdownMenuItem>
        ) : null}

        <DropdownMenuSeparator className="bg-black/5" />

        <DropdownMenuItem
          onSelect={onLogout}
          className="rounded-[14px] px-3 py-2 text-red-600 focus:bg-red-50 focus:text-red-700"
        >
          <LogOut className="mr-2 h-4 w-4" />
          退出登录
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
