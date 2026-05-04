import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import StudentCompetitionHub from './student-competition-hub';
import StudentService from '@/services/student.service';

vi.mock('@/hooks/use-page-activity-refresh', () => ({
  usePageActivityRefresh: vi.fn(),
}));

vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({
    toast: vi.fn(),
  }),
}));

vi.mock('@/hooks/use-student-assessment', () => ({
  useStudentAssessment: vi.fn(() => ({
    needsAssessment: false,
    loading: false,
  })),
}));

vi.mock('@/services/student.service', () => ({
  default: {
    getAvailableDebates: vi.fn(),
    joinDebate: vi.fn(),
  },
}));

describe('StudentCompetitionHub', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(StudentService.getAvailableDebates).mockResolvedValue([]);
  });

  it('routes completed joined debates to the post-match page instead of waiting', async () => {
    vi.mocked(StudentService.getAvailableDebates).mockResolvedValue([
      {
        id: 'debate-001',
        topic: '测试已结束辩论',
        duration: 30,
        status: 'completed',
        invitation_code: 'ABC123',
        created_at: '2026-05-03T00:00:00Z',
        is_joined: true,
      },
    ] as any);

    const onNavigateToPostMatch = vi.fn();
    const onNavigateToWaiting = vi.fn();

    render(
      <StudentCompetitionHub
        onNavigateToPostMatch={onNavigateToPostMatch}
        onNavigateToWaiting={onNavigateToWaiting}
      />
    );

    expect(await screen.findByText('查看赛后分析')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '进入赛后分析页' }));

    expect(onNavigateToPostMatch).toHaveBeenCalledWith('debate-001');
    expect(onNavigateToWaiting).not.toHaveBeenCalled();
  });
});
