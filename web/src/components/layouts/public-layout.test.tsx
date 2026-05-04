import React from 'react';
import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import PublicLayout from './public-layout';

const navigateMock = vi.fn();
const userMenuSpy = vi.fn();

vi.mock('@/store/auth.context', () => ({
  useAuth: vi.fn(),
}));

vi.mock('@/lib/router', () => ({
  useAppRouter: () => ({
    navigate: navigateMock,
  }),
}));

vi.mock('@/components/user-menu', () => ({
  default: (props: any) => {
    userMenuSpy(props);
    return <div data-testid="user-menu" />;
  },
}));

describe('PublicLayout', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('does not expose student-only settings links for a teacher on the public shell', async () => {
    const { useAuth } = await import('@/store/auth.context');
    (useAuth as any).mockReturnValue({
      isAuthenticated: true,
      user: {
        id: 'teacher-001',
        name: '测试老师',
        user_type: 'teacher',
      },
      logout: vi.fn(),
    });

    render(
      <PublicLayout>
        <div>content</div>
      </PublicLayout>
    );

    expect(screen.getByTestId('user-menu')).toBeInTheDocument();
    expect(userMenuSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        onNavigateProfile: undefined,
        onNavigateSecurity: undefined,
      })
    );
  });
});
