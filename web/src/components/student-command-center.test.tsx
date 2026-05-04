import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import StudentCommandCenter from './student-command-center';

const navigateMock = vi.fn();
const getUserInfoMock = vi.fn();
const getSessionStartedAtMock = vi.fn();
const shouldShowPromptMock = vi.fn();
const consumePromptMock = vi.fn();

vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({
    toast: vi.fn(),
  }),
}));

vi.mock('@/hooks/use-page-activity-refresh', () => ({
  usePageActivityRefresh: vi.fn(),
}));

vi.mock('@/hooks/use-student-assessment', () => ({
  useStudentAssessment: vi.fn(),
}));

vi.mock('@/services/student.service', () => ({
  default: {
    getHistory: vi.fn(),
  },
}));

vi.mock('@/lib/router', () => ({
  useAppRouter: () => ({
    navigate: navigateMock,
  }),
}));

vi.mock('@/lib/token-manager', () => ({
  default: {
    getUserInfo: getUserInfoMock,
    getSessionStartedAt: getSessionStartedAtMock,
  },
}));

vi.mock('@/lib/student-assessment-onboarding', () => ({
  shouldShowAssessmentOnboardingPrompt: (...args: unknown[]) =>
    shouldShowPromptMock(...args),
  consumeAssessmentOnboardingPrompt: (...args: unknown[]) =>
    consumePromptMock(...args),
}));

describe('StudentCommandCenter', () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    sessionStorage.clear();

    const { useStudentAssessment } = await import('@/hooks/use-student-assessment');
    const StudentService = (await import('@/services/student.service')).default;

    (useStudentAssessment as any).mockReturnValue({
      assessment: null,
      analytics: {
        completed_debates: 0,
        average_score: 85,
        total_debates: 2,
      },
      needsAssessment: true,
      loading: false,
    });

    (StudentService.getHistory as any).mockResolvedValue({
      list: [],
      total: 0,
      page: 1,
      page_size: 8,
    });

    getUserInfoMock.mockReturnValue({
      id: 'student-001',
      account: 'student-001',
      user_type: 'student',
    });
    getSessionStartedAtMock.mockReturnValue(123456);
    shouldShowPromptMock.mockReturnValue(true);
  });

  it('shows the onboarding prompt once and consumes it when deferred', async () => {
    render(<StudentCommandCenter />);

    expect(
      await screen.findByText('先完成能力评估，再进入正式比赛流程')
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '稍后评估' }));

    expect(consumePromptMock).toHaveBeenCalled();
    await waitFor(() => {
      expect(
        sessionStorage.getItem('assessment_prompt_dismissed:student-home:123456')
      ).toBe('1');
    });
  });

  it('uses router navigation when entering the competition area', async () => {
    const { useStudentAssessment } = await import('@/hooks/use-student-assessment');
    (useStudentAssessment as any).mockReturnValue({
      assessment: { is_default: false },
      analytics: {
        completed_debates: 1,
        average_score: 90,
        total_debates: 4,
      },
      needsAssessment: false,
      loading: false,
    });
    shouldShowPromptMock.mockReturnValue(false);

    render(<StudentCommandCenter />);

    fireEvent.click(await screen.findByRole('button', { name: '前往比赛区' }));

    expect(navigateMock).toHaveBeenCalledWith('/student/competition');
  });
});
