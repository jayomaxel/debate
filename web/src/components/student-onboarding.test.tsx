import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import StudentOnboarding from './student-onboarding';
import StudentService, { type Debate } from '@/services/student.service';

vi.mock('@/hooks/use-page-activity-refresh', () => ({
  usePageActivityRefresh: vi.fn(),
}));

vi.mock('@/services/student.service', () => ({
  default: {
    getAvailableDebates: vi.fn(),
    getDebateParticipants: vi.fn(),
  },
}));

vi.mock('@/store/auth.context', () => ({
  useAuth: () => ({
    user: {
      id: 'student-001',
      name: '测试学生',
    },
  }),
}));

vi.mock('./waiting-status-bar', () => ({
  default: ({
    hasAssignedRole,
    participantCount,
    isReady,
  }: {
    hasAssignedRole: boolean;
    participantCount: number;
    isReady: boolean;
  }) => (
    <div>
      WaitingStatusBar {String(hasAssignedRole)} {participantCount} {String(isReady)}
    </div>
  ),
}));

vi.mock('./debate-topic-card', () => ({
  default: ({ debate }: { debate: Debate }) => <div>DebateTopicCard {debate.topic}</div>,
}));

const baseDebate: Debate = {
  id: 'debate-001',
  topic: 'AI 是否应该替代部分教师工作',
  description: '测试辩题',
  duration: 30,
  status: 'published',
  invitation_code: 'ABC123',
  created_at: '2026-05-03T00:00:00Z',
  participant_count: 3,
  is_joined: true,
  role: 'debater_2',
  role_reason: '负责推进攻辩并追问对方论证。',
  participants: [
    {
      user_id: 'student-001',
      name: '测试学生',
      role: 'debater_2',
      role_reason: '负责推进攻辩并追问对方论证。',
    },
    {
      user_id: 'student-002',
      name: '队友甲',
      role: 'debater_1',
    },
    {
      user_id: 'student-003',
      name: '队友乙',
      role: 'debater_3',
    },
  ],
};

describe('StudentOnboarding', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(StudentService.getAvailableDebates).mockResolvedValue([]);
    vi.mocked(StudentService.getDebateParticipants).mockResolvedValue([]);
  });

  it('shows an empty-state prompt when the student has not joined a debate yet', async () => {
    render(<StudentOnboarding />);

    expect(await screen.findByText('还没有加入本场辩论')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '返回学生首页' })).toBeInTheDocument();
  });

  it('renders the merged waiting and preparation view for a joined debate', async () => {
    vi.mocked(StudentService.getAvailableDebates).mockResolvedValue([baseDebate]);

    render(<StudentOnboarding />);

    expect(await screen.findByText('等待与准备页')).toBeInTheDocument();
    expect(screen.getByText('DebateTopicCard AI 是否应该替代部分教师工作')).toBeInTheDocument();
    expect(screen.getByText('WaitingStatusBar true 3 true')).toBeInTheDocument();
    expect(screen.getByText('邀请码 ABC123')).toBeInTheDocument();
    expect(screen.getByText('我的辩位')).toBeInTheDocument();
    expect(screen.getByText('二辩')).toBeInTheDocument();
    expect(screen.getByText('测试学生')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '进入正式辩论' })).toBeEnabled();
  });

  it('loads participants on demand when the joined debate is missing roster data', async () => {
    vi.mocked(StudentService.getAvailableDebates).mockResolvedValue([
      {
        ...baseDebate,
        participants: [],
        participant_count: 1,
      },
    ]);
    vi.mocked(StudentService.getDebateParticipants).mockResolvedValue([
      {
        user_id: 'student-001',
        name: '测试学生',
        role: 'debater_2',
        role_reason: '负责推进攻辩并追问对方论证。',
      },
    ]);

    render(<StudentOnboarding />);

    expect(await screen.findByText('测试学生')).toBeInTheDocument();
    await waitFor(() => {
      expect(StudentService.getDebateParticipants).toHaveBeenCalledWith('debate-001');
    });
  });

  it('uses the provided callbacks for entering the debate and opening analytics', async () => {
    vi.mocked(StudentService.getAvailableDebates).mockResolvedValue([baseDebate]);
    const onDebateStart = vi.fn();
    const onNavigateToAnalytics = vi.fn();

    render(
      <StudentOnboarding
        onDebateStart={onDebateStart}
        onNavigateToAnalytics={onNavigateToAnalytics}
      />
    );

    fireEvent.click(await screen.findByRole('button', { name: '进入正式辩论' }));
    fireEvent.click(screen.getByRole('button', { name: '查看成长区' }));
    fireEvent.click(screen.getByRole('button', { name: '查看历史记录' }));

    expect(onDebateStart).toHaveBeenCalledWith('debate-001');
    expect(onNavigateToAnalytics).toHaveBeenNthCalledWith(1, 'growth');
    expect(onNavigateToAnalytics).toHaveBeenNthCalledWith(2, 'history');
  });
});
