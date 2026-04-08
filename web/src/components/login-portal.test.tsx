import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import LoginPortal from './login-portal';
import { useAuth } from '@/store/auth.context';
import { useToast } from '@/hooks/use-toast';
import AuthService from '@/services/auth.service';

const loginMock = vi.fn();
const toastMock = vi.fn();

vi.mock('@/store/auth.context', () => ({
  useAuth: vi.fn(),
}));

vi.mock('@/hooks/use-toast', () => ({
  useToast: vi.fn(),
}));

vi.mock('@/services/auth.service', () => ({
  default: {
    getPublicClasses: vi.fn(),
    registerStudent: vi.fn(),
    registerTeacher: vi.fn(),
  },
}));

describe('LoginPortal', () => {
  const switchToRegisterMode = async () => {
    act(() => {
      fireEvent.click(screen.getByRole('button', { name: '注册' }));
    });

    await waitFor(() => {
      expect(screen.getByText('欢迎注册')).toBeInTheDocument();
    });
  };

  const activateRoleTab = async (roleName: string) => {
    act(() => {
      fireEvent.mouseDown(screen.getByRole('tab', { name: roleName }));
    });

    await waitFor(() => {
      expect(screen.getByRole('tab', { name: roleName })).toHaveAttribute('aria-selected', 'true');
    });
  };

  beforeEach(() => {
    vi.clearAllMocks();

    (useAuth as any).mockReturnValue({
      login: loginMock,
    });

    (useToast as any).mockReturnValue({
      toast: toastMock,
    });

    (AuthService.getPublicClasses as any).mockResolvedValue([]);
    (AuthService.registerStudent as any).mockResolvedValue({
      id: 'student-001',
    });
    (AuthService.registerTeacher as any).mockResolvedValue({
      id: 'teacher-001',
    });
  });

  it('hides administrator registration and resets the selected role back to student', async () => {
    render(<LoginPortal onLogin={vi.fn()} />);

    await activateRoleTab('管理员');
    expect(screen.getByRole('button', { name: '登录管理控制台' })).toBeInTheDocument();

    await switchToRegisterMode();

    await waitFor(() => {
      expect(screen.queryByRole('tab', { name: '管理员' })).not.toBeInTheDocument();
    });

    expect(screen.getAllByRole('tab')).toHaveLength(2);
    expect(screen.getByRole('tab', { name: '我是学生' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.queryByText('管理员账号')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '登录管理控制台' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '注册账号' })).toBeInTheDocument();
  });

  it('shows a confirm-password field in register mode for student and teacher', async () => {
    render(<LoginPortal onLogin={vi.fn()} />);

    await switchToRegisterMode();

    expect(screen.getByLabelText(/确认密码/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '注册账号' })).toBeInTheDocument();

    await activateRoleTab('我是老师');

    expect(screen.getByLabelText(/确认密码/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '注册账号' })).toBeInTheDocument();
  });

  it('blocks registration when the password confirmation does not match', async () => {
    render(<LoginPortal onLogin={vi.fn()} />);

    await switchToRegisterMode();

    fireEvent.change(screen.getByLabelText(/账号/), {
      target: { value: 'student-001' },
    });
    fireEvent.change(screen.getByLabelText(/^密码/), {
      target: { value: 'secret-123' },
    });
    fireEvent.change(screen.getByLabelText(/确认密码/), {
      target: { value: 'secret-456' },
    });
    fireEvent.change(screen.getByLabelText('姓名'), {
      target: { value: '测试学生' },
    });

    fireEvent.click(screen.getByRole('button', { name: '注册账号' }));

    await waitFor(() => {
      expect(toastMock).toHaveBeenCalledWith(
        expect.objectContaining({
          variant: 'destructive',
          title: '注册失败',
          description: '两次输入的密码不一致',
        })
      );
    });

    expect(AuthService.registerStudent).not.toHaveBeenCalled();
  });
});
